import asyncio
from collections.abc import Iterable
from hashlib import md5

from pydantic import BaseModel, TypeAdapter

from vehicle_controller.async_value import AsyncValue
from vehicle_controller.nats import NATS, Msg, with_cleanup_sub
from vehicle_controller.resilience import run_background_task
from vehicle_controller.worker.vehicle import VehicleConfig, run_vehicle_controller


def _belongs_to_worker(
    worker_id: str,
    worker_ids: Iterable[str],
    resource_id: str,
) -> bool:
    print(worker_ids)

    def get_hash(key: str) -> int:
        return int(md5(key.encode("utf-8")).hexdigest(), 16)

    # Calculate hashes for dictionary of {hash: worker_id}
    worker_ring: list[tuple[int, str]] = []
    for uid in worker_ids:
        worker_ring.append((get_hash(uid), uid))

    # Sort by hash to form the ring
    worker_ring.sort()

    resource_hash = get_hash(resource_id)

    # Find the first worker with a hash >= resource_hash
    target_worker = None
    for w_hash, w_id in worker_ring:
        if w_hash >= resource_hash:
            target_worker = w_id
            break

    # Wrap around to the first worker if no worker has a higher hash
    if target_worker is None:
        target_worker = worker_ring[0][1]

    return target_worker == worker_id


class ResponseUpdate(BaseModel):
    vehicles: list[VehicleConfig]


class ResponseDelete(BaseModel):
    vehicle_ids: list[str]


DeltaResponse = ResponseUpdate | ResponseDelete
DeltaResponseAdapter = TypeAdapter[DeltaResponse](DeltaResponse)


async def run_workers(
    nc: NATS,
    worker_id: str,
    q_worker_ids: AsyncValue[list[str]],
    sub_veh_broadcast_deltas: str,
    sub_veh_listen: str,
    sub_veh_cmd: str,
    sub_veh_status: str,
):
    worker_ids = frozenset[str]()
    known_vehicles: dict[str, VehicleConfig] = {}

    async with asyncio.TaskGroup() as tg:
        tasks_veh: dict[str, asyncio.Task[None]] = {}

        def cancel_veh(vehicle_id: str):
            if vehicle_id not in tasks_veh:
                return
            tasks_veh[vehicle_id].cancel()
            del tasks_veh[vehicle_id]

        def add_veh(vehicle_config: VehicleConfig):
            known_vehicles[vehicle_config.vehicle_id] = vehicle_config
            if not _belongs_to_worker(worker_id, worker_ids, vehicle_config.vehicle_id):
                return
            cancel_veh(vehicle_config.vehicle_id)
            tasks_veh[vehicle_config.vehicle_id] = tg.create_task(
                run_background_task(
                    lambda vc=vehicle_config: run_vehicle_controller(
                        nc,
                        vc,
                        f"{sub_veh_cmd}.{vehicle_config.vehicle_id}",
                        f"{sub_veh_status}.{vehicle_config.vehicle_id}",
                    ),
                    f"vehicle-{vehicle_config.vehicle_id}",
                )
            )

        def remove_veh(vehicle_id: str):
            if vehicle_id in known_vehicles:
                del known_vehicles[vehicle_id]
            cancel_veh(vehicle_id)

        async def on_delta(msg: Msg):
            match delta := DeltaResponseAdapter.validate_json(msg.data):
                case ResponseUpdate():
                    for veh in delta.vehicles:
                        add_veh(veh)
                case ResponseDelete():
                    for vid in delta.vehicle_ids:
                        remove_veh(vid)

        async def rebalance_loop():
            nonlocal worker_ids

            while True:
                other_worker_ids, wait_for_worker_ids = q_worker_ids.get()
                worker_ids = frozenset(other_worker_ids) | {worker_id}

                for vid in tasks_veh:
                    if not _belongs_to_worker(worker_id, worker_ids, vid):
                        cancel_veh(vid)
                for veh in known_vehicles.values():
                    add_veh(veh)

                await wait_for_worker_ids()

        task_rebalance = tg.create_task(rebalance_loop())  # noqa: F841

        async with with_cleanup_sub(
            await nc.subscribe(sub_veh_broadcast_deltas, cb=on_delta)
        ):
            delta = ResponseUpdate.model_validate_json(
                (await nc.request(sub_veh_listen, b"")).data
            )
            for veh in delta.vehicles:
                add_veh(veh)
            await asyncio.Future()
