import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol

from fastapi import FastAPI
from fastapi_problem.handler import add_exception_handler

from vehicle_controller import health
from vehicle_controller.errors import eh
from vehicle_controller.nats import NATS
from vehicle_controller.settings import Settings


@asynccontextmanager
async def with_nats(nats_url):
    nc = NATS()
    while True:
        try:
            await nc.connect(
                nats_url,
                allow_reconnect=True,
                max_reconnect_attempts=-1,
            )
            break
        except Exception:
            await asyncio.sleep(2)
    try:
        yield nc
    finally:
        await nc.close()


class MakeApp[T: Settings](Protocol):
    def __call__(self, settings: T | None = None) -> FastAPI: ...


def make_app_fn[T: Settings](
    settings_type: type[T],
    inner_lifespan: Callable[[FastAPI], AbstractAsyncContextManager[None]],
) -> MakeApp[T]:
    def make_app(settings: T | None = None):
        if settings is None:
            settings = settings_type()  # type: ignore

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with with_nats(settings.nats_url) as nc:
                app.state.settings = settings
                app.state.nc = nc
                add_exception_handler(app, eh)

                app.include_router(health.router, prefix="/health")

                async with inner_lifespan(app):
                    yield

        return FastAPI(lifespan=lifespan)

    return make_app
