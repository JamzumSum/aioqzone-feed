import asyncio
import io
from contextlib import suppress
from os import environ

import pytest
import pytest_asyncio
from aioqzone.api import UpLoginConfig, UpLoginManager
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from qqqr.utils.net import ClientAdapter

loginman_list = ["up"]
if environ.get("CI") is None:
    loginman_list.append("qr")


class test_env(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="test_")
    uin: int = 0
    password: SecretStr = Field(default="")


@pytest.fixture(scope="session")
def env():
    return test_env()


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def client():
    async with ClientAdapter() as client:
        yield client


@pytest.fixture(params=loginman_list)
def man(request, client: ClientAdapter, env: test_env):
    if request.param == "up":
        return UpLoginManager(client, UpLoginConfig(uin=env.uin, pwd=env.password))

    if request.param == "qr":
        from aioqzone.api import QrLoginConfig, QrLoginManager

        man = QrLoginManager(client, QrLoginConfig(uin=env.uin))
        with suppress(ImportError):
            from PIL import Image as image

            man.qr_fetched.add_impl(
                lambda png, times, qr_renew=False: (
                    image.open(io.BytesIO(png)).show() if png else None
                )
            )

        return man
