import asyncio
from typing import Type
from unittest.mock import patch

import pytest
import pytest_asyncio
from aioqzone.api import QzoneWebAPI
from aioqzone.api.loginman import MixedLoginMan
from aioqzone.event import LoginMethod
from aioqzone.exception import LoginError, QzoneError, SkipLoginInterrupt
from httpx import ConnectError, HTTPError, HTTPStatusError, TimeoutException
from qqqr.event.login import UpEvent
from qqqr.exception import HookError, UserBreak
from qqqr.utils.net import ClientAdapter

from aioqzone_feed.api import HeartbeatApi
from aioqzone_feed.event import HeartbeatEvent

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(scope="module")
async def api(client: ClientAdapter, man: MixedLoginMan):
    api = HeartbeatApi(QzoneWebAPI(client, man))
    api.register_hook(HeartbeatEvent())
    yield api
    api.stop()


@pytest.mark.parametrize(
    "exc2r,should_alive",
    [
        (LoginError("mock", [LoginMethod.up, LoginMethod.qr]), False),
        (SystemExit(), False),
        (LoginError("mock", [LoginMethod.qr]), True),
        (ConnectError("mock"), True),
        (TimeoutException("mock"), True),
        (HTTPStatusError("mock", request=..., response=...), True),  # type: ignore
        (HTTPError("mock"), True),
        (QzoneError(-3000), True),
        (SkipLoginInterrupt(), True),
        (UserBreak(), True),
        (asyncio.CancelledError(), True),
        (HookError(UpEvent.GetSmsCode), False),
    ],
)
async def test_heartbeat_exc(api: HeartbeatApi, exc2r: Type[BaseException], should_alive: bool):
    from aioqzone.api import QzoneWebAPI

    with patch.object(QzoneWebAPI, "get_feeds_count", side_effect=exc2r):
        api.add_heartbeat(retry=2, hb_intv=0.1, retry_intv=0)
        assert api.hb_timer
        await asyncio.sleep(0.4)
        assert (api.hb_timer.state == "PENDING") is should_alive
