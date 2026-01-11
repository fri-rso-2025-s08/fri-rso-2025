import asyncio

from vehicle_controller.nats import NATS, Msg
from vehicle_controller.shared import Heartbeat


async def run_heartbeat(
    nc: NATS,
    worker_id: str,
    subject_heartbeat_req: str,
    subject_heartbeat_resp: str,
):
    async def send_heartbeat(active: bool):
        hb = Heartbeat(worker_id=worker_id, active=active)
        await nc.publish(subject_heartbeat_resp, hb.model_dump_json().encode("utf-8"))

    async def message_handler(msg: Msg):
        await send_heartbeat(True)

    sub = await nc.subscribe(subject_heartbeat_req, cb=message_handler)

    try:
        await send_heartbeat(active=True)
        await asyncio.Future()
    finally:
        try:
            await send_heartbeat(active=False)
        finally:
            await sub.unsubscribe()
