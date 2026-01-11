from typing import Annotated

from fastapi import Depends, FastAPI, Request
from nats.aio.client import Client as NATS
from nats.aio.msg import Msg


async def get_nats_from_fastapi(app: FastAPI) -> NATS:
    nc: NATS = app.state.nc
    return nc


async def get_nats(request: Request) -> NATS:
    return await get_nats_from_fastapi(request.app)


GetNats = Annotated[NATS, Depends(get_nats)]


__all__ = [
    "NATS",
    "GetNats",
    "Msg",
    "get_nats",
    "get_nats_from_fastapi",
]
