from typing import cast

import lazy_object_proxy
from fastapi import FastAPI

from vehicle_manager.settings import Settings


def make_app(*, settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()  # type: ignore

    app = FastAPI()

    return app


app = cast(FastAPI, lazy_object_proxy.Proxy(make_app))
