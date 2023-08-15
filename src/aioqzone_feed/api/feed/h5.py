import asyncio
import logging
import time
from typing import Optional

from aioqzone.api import Loginable
from aioqzone.api.h5 import QzoneH5API
from aioqzone.exception import LoginError
from aioqzone.model import FeedData
from aioqzone.utils.catch import HTTPStatusErrorDispatch, QzoneErrorDispatch
from qqqr.exception import UserBreak
from qqqr.utils.net import ClientAdapter

from aioqzone_feed.api.heartbeat import HeartbeatApi
from aioqzone_feed.message import FeedApiEmitterMixin
from aioqzone_feed.message.feed import TY_BID
from aioqzone_feed.type import FeedContent
from aioqzone_feed.utils.exc_barrier import ExcBarrier

log = logging.getLogger(__name__)
login_exc = (LoginError, UserBreak, asyncio.CancelledError)


class FeedH5Api(FeedApiEmitterMixin[FeedData], QzoneH5API):
    """
    .. versionadded:: 0.13.0
    """

    def __init__(self, client: ClientAdapter, loginman: Loginable, *, init_hb=True):
        super().__init__(client, loginman)
        self.bid = -1
        if init_hb:
            self.hb_api = HeartbeatApi(self)

    def new_batch(self) -> TY_BID:
        """
        The new_batch function edit internal batch id and return it.

        A batch id can be used to identify a batch, thus even the same feed can have different id e.g. `(bid, uin, abstime)`.

        :rtype: :obj:`TY_BID`
        :return: The batch_id.
        """

        self.bid += 1
        return self.bid

    async def get_feeds_by_count(self, count: int = 10) -> int:
        """Get feeds by count.

        :param count: feeds count to get, max as 10, defaults to 10

        :raise `qqqr.exception.UserBreak`: qr login canceled
        :raise `aioqzone.exception.LoginError`: not logined
        :raise `QzoneError`: when code not in -(3000, -10000)
        :raise `HTTPStatusError`: when code != 403
        :raise `ExceptionGroup`: max retry exceeds

        :return: number of feeds that we got actually.

        .. note:: You may need :meth:`.new_batch` to generate a new batch id.
        """
        stop_fetching = False
        got = 0
        attach_info = ""
        errs = ExcBarrier()
        feeds = []

        def error_dispatch(e):
            feeds.clear()
            errs.append(e)
            log.warning(f"error fetching page: {e}")

        while not stop_fetching:
            with QzoneErrorDispatch() as qse, HTTPStatusErrorDispatch() as hse:
                qse.dispatch(-3000, -10000, dispatcher=error_dispatch)
                hse.dispatch(403, dispatcher=error_dispatch)
                resp = await self.get_active_feeds(attach_info)
                attach_info = resp.attachinfo
                feeds = resp.vFeeds
                stop_fetching = not resp.hasmore

            log.debug(attach_info, extra=dict(got=got))

            for fd in feeds[: count - got]:
                if await self.stop_fetch(fd):
                    stop_fetching = True
                    continue
                if (got := got + 1) >= count:
                    stop_fetching = True
                    break
                self._dispatch_feed(fd)

        return got

    async def get_feeds_by_second(
        self,
        seconds: float,
        start: Optional[float] = None,
    ) -> int:
        """Get feeds by abstime (seconds). Range: [`start` - `seconds`, `start`].

        :param seconds: filter on abstime, calculate from `start`.
        :param start: start timestamp, defaults to None, means now.
        :param exceed_pred: another criterion to judge if the feed is out of range, defaults to None

        :raise `qqqr.exception.UserBreak`: qr login canceled
        :raise `aioqzone.exception.LoginError`: not logined
        :raise `QzoneError`: when code not in -(3000, -10000)
        :raise `HTTPStatusError`: when code != 403
        :raise `ExceptionGroup`: max retry exceeds

        :return: feeds num got actually.

        .. note:: You may need :meth:`.new_batch` to generate a new batch id.
        """
        start = start or time.time()
        end = start - seconds
        stop_fetching = False
        got = 0
        attach_info = ""
        errs = ExcBarrier()
        feeds = []

        def error_dispatch(e):
            feeds.clear()
            errs.append(e)
            log.warning(f"error fetching page: {e}")

        while not stop_fetching:
            with QzoneErrorDispatch() as qse, HTTPStatusErrorDispatch() as hse:
                qse.dispatch(-3000, -10000, dispatcher=error_dispatch)
                hse.dispatch(403, dispatcher=error_dispatch)
                resp = await self.get_active_feeds(attach_info)
                attach_info = resp.attachinfo
                feeds = resp.vFeeds
                stop_fetching = not resp.hasmore

            log.debug(attach_info, extra=dict(got=got))

            for fd in feeds:
                if fd.abstime > start:
                    continue
                if fd.abstime < end or await self.stop_fetch(fd):
                    stop_fetching = True
                    continue
                got += 1
                self._dispatch_feed(fd)

        return got

    def drop_rule(self, feed: FeedData) -> bool:
        """Drop feeds according to some rules.
        No need to emit :meth:`FeedEvent.FeedDropped` event, it is handled by :meth:`_dispatch_feed`.

        Subclasses may inherit this method to customize their own rules.

        :param feed: the feed
        :return: if the feed is dropped.
        """
        if feed.userinfo.uin == 20050606:
            log.info(f"advertisement rule hit: {feed.userinfo.uin}")
            log.debug(f"Dropped: {feed}")
            return True

        if feed.fid.startswith("advertisement"):
            log.info(f"advertisement rule hit: {feed.fid}")
            log.debug(f"Dropped: {feed}")
            return True

        return False

    def _dispatch_feed(self, feed: FeedData) -> None:
        """dispatch feed according to api support.

        1. Drop feed according to rules defined in `drop_rule`, trigger :meth:`FeedDropped` hook if dropped;
        2. Get more if `hasmore` flag is set to ``1`` (Not Implemented yet);
        3. Trigger :meth:`FeedProcEnd` for prcocessed feeds.

        :param feed: feed
        """
        if feed.summary.hasmore:
            self.ch_dispatch.add_awaitable(
                self.shuoshuo(feed.fid, feed.userinfo.uin, feed.common.appid)
            ).add_done_callback(lambda t: self._dispatch_feed(t.result()))
            return

        model = FeedContent.from_feed(feed)

        if self.drop_rule(feed):
            FeedContent.from_feed(feed)
            self.ch_dispatch.add_awaitable(self.feed_dropped.emit(self.bid, model))
            return

        model.set_detail(feed)
        self.ch_notify.add_awaitable(self.feed_processed.emit(self.bid, model))

    def stop(self) -> None:
        """Clear **all** registered tasks. All tasks will be CANCELLED if not finished."""
        log.warning("FeedApi stopping...")
        super().stop()
        if hasattr(self, "hb_api"):
            self.hb_api.stop()
