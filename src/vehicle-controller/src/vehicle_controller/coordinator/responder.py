from vehicle_controller.async_value import AsyncValue
from vehicle_controller.nats import NATS, Msg, with_cleanup_sub
from vehicle_controller.shared import WorkerIds


async def run_responder(
    nc: NATS,
    q_worker_ids: AsyncValue[list[str]],
    sub_broadcast: str,
    sub_listen: str,
):
    current_worker_ids: list[str] = []

    async def listener(msg: Msg):
        await msg.respond(
            WorkerIds(worker_ids=current_worker_ids).model_dump_json().encode("utf-8")
        )

    async with with_cleanup_sub(await nc.subscribe(sub_listen, cb=listener)):
        while True:
            current_worker_ids, wait = q_worker_ids.get()
            await nc.publish(
                sub_broadcast,
                WorkerIds(worker_ids=current_worker_ids)
                .model_dump_json()
                .encode("utf-8"),
            )
            await wait()
