import asyncio
from typing import Type
from unittest.mock import patch

import pytest
import pytest_asyncio
from aioqzone.api import QzoneH5API, UnifiedLoginManager
from aioqzone.exception import LoginError, QzoneError, SkipLoginInterrupt
from httpx import ConnectError, HTTPError, TimeoutException
from qqqr.exception import UserBreak
from qqqr.utils.net import ClientAdapter

from aioqzone_feed.api import HeartbeatApi

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def api(client: ClientAdapter, man: UnifiedLoginManager):
    api = HeartbeatApi(QzoneH5API(client, man))
    yield api
    api.stop()


@pytest.mark.parametrize(
    "exc2r,should_alive",
    [
        (LoginError(dict.fromkeys(["up", "qr"], "mock")), False),
        (SystemExit(), False),
        (LoginError(dict.fromkeys(["qr"], "mock")), True),
        (ConnectError("mock"), True),
        (TimeoutException("mock"), True),
        (HTTPError("mock"), True),
        (QzoneError(-3000), False),
        (QzoneError(-3000, "请先登录"), False),
        (SkipLoginInterrupt(), True),
        (UserBreak(), True),
        (asyncio.CancelledError(), True),
    ],
)
async def test_heartbeat_exc(api: HeartbeatApi, exc2r: Type[BaseException], should_alive: bool):
    pool = []
    api.hb_failed.add_impl(lambda exc, stop: pool.append(stop))
    with patch.object(api, "hb_api", side_effect=exc2r):
        await api.heartbeat_refresh()
        await api.ch_hb.wait()
        assert pool
        assert not pool[0] is should_alive
