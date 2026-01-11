import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

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


def with_retries[**T, R: Awaitable[Any]](
    n_retries: int, t_between: float
) -> Callable[[Callable[T, R]], Callable[T, R]]:
    def wrap(fn: Callable[T, R]):
        async def wrapped(*args: T.args, **kwargs: T.kwargs):
            for i in range(n_retries):
                try:
                    return await fn(*args, **kwargs)
                except Exception as e:
                    if i == n_retries - 1:
                        raise
                    logger.warning("Retrying function %s.", fn, exc_info=e)
                    await asyncio.sleep(t_between)
            raise RuntimeError("unreachable")

        return wrapped

    return wrap  # type: ignore
