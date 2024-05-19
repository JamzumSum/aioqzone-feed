import asyncio
import logging
from os import environ as env

from aiohttp import ClientSession
from aioqzone.api import UpLoginConfig, UpLoginManager
from tenacity import RetryError

from aioqzone_feed.api import FeedApi

n_dropped = 0
log = logging.getLogger(__name__)


async def amain():
    async with ClientSession() as client:
        # 实例化一个账密登录器。目前来说二维码登录器要更稳妥一些。
        # 如果不改动代码的话，那么需要设置 uin 和 pwd 两个环境变量。
        loginable = UpLoginManager(client, UpLoginConfig.model_validate(env))
        # 实例化一个API对象
        api = FeedApi(client, loginable)

        # 接收舍弃的动态。程序中有一些内建的规则，您也可以重载 drop_rule. 舍弃的动态包含的字段要少一些。
        api.feed_dropped.add_impl(log_dropped_feeds)
        # 回调可以有多个，同步异步函数都可以，会按顺序调用。异常的回调会被忽略，之后的继续执行。
        api.feed_dropped.add_impl(drop_statistic)

        # 当然，也可以用装饰器的写法。
        @api.feed_processed.add_impl
        async def send_to_user(bid: int, feed):
            if bid != batch_id:
                # 如果不知道怎么处理的话，丢掉就好了
                return

            # 这里你就得到一条动态了，可以做你想做的操作
            await send_feed(feed)

        # =======================================================
        # =======================================================
        # 以上都是准备工作，可以在初始化的时候完成。下面是每次爬取都要做的。

        # 获取一个 batch id，可以用来判断一个回调是哪次爬取触发的
        # 这是一个可选的步骤。不过还是推荐这样做。
        batch_id = api.new_batch()

        try:
            # 爬取三天内的动态
            n = await api.get_feeds_by_second(3 * 86400)
            # 爬取到了多少动态可以马上返回，但动态的处理结果是通过回调下发的
            # 也就是说，n 表示总共爬取了多少条动态
            # 但动态内容需要注册 feed_processed 来获取
        except RetryError as e:
            log.error("登录错误", exc_info=e.last_attempt.exception())
            return

        # 调用 wait 表示阻塞等待所有动态处理完毕
        # 在此期间 feed_processed 和 feed_dropped 两种信号会不断被发送，直到所有动态处理完毕
        await api.wait()
        # 到这里 一个爬取流程就结束了


async def log_dropped_feeds(bid: int, feed):
    log.debug(feed)


def drop_statistic(bid: int, feed):
    global n_dropped
    n_dropped += 1


if __name__ == "__main__":
    asyncio.run(amain())
