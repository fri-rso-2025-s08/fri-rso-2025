import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


async def run_background_task(coro: Callable[[], Awaitable[None]], name: str):
    while True:
        try:
            await coro()
            logger.warning("Background task %r terminated, restarting.", name)
        except Exception as e:
            logger.warning(
                "Background task %r raised exception, restarting.", name, exc_info=e
            )
        await asyncio.sleep(1)
