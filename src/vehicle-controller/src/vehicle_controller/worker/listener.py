import asyncio

from vehicle_controller.async_value import AsyncValue
from vehicle_controller.nats import NATS, Msg, with_cleanup_sub
from vehicle_controller.shared import WorkerIds


async def run_listener(
    nc: NATS,
    sub_broadcast: str,
    sub_listen: str,
    out: AsyncValue[list[str]],
):
    async def on_msg(msg: Msg):
        await out.put(WorkerIds.model_validate_json(msg.data).worker_ids)

    async with with_cleanup_sub(await nc.subscribe(sub_broadcast, cb=on_msg)):
        await on_msg(await nc.request(sub_listen, b""))
        await asyncio.Future()
