import asyncio
from time import time

from vehicle_controller.async_value import AsyncValue
from vehicle_controller.nats import NATS, Msg, with_cleanup_sub
from vehicle_controller.shared import Heartbeat


async def run_coordinator(
    nc: NATS,
    sub_heartbeat_req: str,
    sub_heartbeat_resp: str,
    heartbeat_interval: float,
    heartbeat_missed_limit: int,
    out: AsyncValue[list[str]],
):
    clients: dict[str, float] = {}

    async def send_clients():
        await out.put(list(clients))

    async def message_handler(msg: Msg):
        should_send = False
        hb = Heartbeat.model_validate_json(msg.data)

        if hb.active:
            if hb.worker_id not in clients:
                should_send = True
            clients[hb.worker_id] = time()
        else:
            if hb.worker_id in clients:
                should_send = True
                del clients[hb.worker_id]

        if should_send:
            await send_clients()

    await send_clients()

    async with with_cleanup_sub(
        await nc.subscribe(sub_heartbeat_resp, cb=message_handler)
    ):
        while True:
            await nc.publish(sub_heartbeat_req, b"")

            now = time()
            threshold = heartbeat_interval * heartbeat_missed_limit + 0.5

            to_evict = []

            for cid, last_seen in clients.items():
                if now - last_seen > threshold:
                    to_evict.append(cid)

            for cid in to_evict:
                del clients[cid]

            if to_evict:
                await send_clients()

            await asyncio.sleep(heartbeat_interval)
