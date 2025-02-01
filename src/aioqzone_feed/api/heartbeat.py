import logging

from aiohttp.client_exceptions import ClientConnectorError, ClientResponseError, ServerTimeoutError
from aioqzone.api.h5 import QzoneH5API
from tenacity import RetryError

from aioqzone_feed.message import HeartbeatEmitterMixin

log = logging.getLogger(__name__)
known_exc = (ClientResponseError, ServerTimeoutError)


class HeartbeatApi(HeartbeatEmitterMixin, QzoneH5API):
    async def heartbeat_refresh(self) -> None:
        """A wrapper function that calls :obj:`hb_api` and handles all kinds of excpetions
        raised during heartbeat.

        .. note::
            This method calls heartbeat **ONLY ONCE** so it should be called periodically by using
            other timer/scheduler.

        .. versionchanged:: 0.13.4

            do not retry, just call heartbeat once
        """

        try:
            cnt = (await self.mfeeds_get_count()).active_cnt
            log.debug("heartbeat: active_cnt=%d", cnt)
            if cnt > 0:
                self.ch_heartbeat_notify.add_awaitable(self.hb_refresh.emit(cnt))
            return
        except ClientConnectorError as e:
            log.warning("网络连接较差，或许可以稍后再试。")
            self.ch_heartbeat_notify.add_awaitable(self.hb_failed.emit(e))
        except RetryError as e:
            if e.last_attempt.failed:
                e = e.last_attempt.exception()
                assert e is not None
            log.warning(e)
            self.ch_heartbeat_notify.add_awaitable(self.hb_failed.emit(e))
        except known_exc as e:
            log.warning(e)
            self.ch_heartbeat_notify.add_awaitable(self.hb_failed.emit(e))
        except BaseException as e:
            log.error("心跳出现未捕获的异常", exc_info=e)
            self.ch_heartbeat_notify.add_awaitable(self.hb_failed.emit(e))

    def stop(self) -> None:
        """Clear **all** registered tasks. All tasks will be CANCELLED if not finished."""
        log.warning("HeartbeatApi stopping...")
        super().stop()
