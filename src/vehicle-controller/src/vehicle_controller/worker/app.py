import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI

from vehicle_controller.app import make_app_fn
from vehicle_controller.async_value import AsyncValue
from vehicle_controller.nats import get_nats_from_fastapi
from vehicle_controller.resilience import run_background_task
from vehicle_controller.settings import get_settings_from_fastapi
from vehicle_controller.worker.heartbeat import run_heartbeat
from vehicle_controller.worker.listener import run_listener
from vehicle_controller.worker.settings import WorkerSettings
from vehicle_controller.worker.workers import run_workers


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings_from_fastapi(app, t=WorkerSettings)
    nc = await get_nats_from_fastapi(app)
    worker_id = str(uuid4())
    q_worker_ids = AsyncValue[list[str]]([])

    async with asyncio.TaskGroup() as tg:
        task_heartbeat = tg.create_task(
            run_background_task(
                lambda: run_heartbeat(
                    nc,
                    worker_id,
                    f"{settings.sub_heartbeat}.req",
                    f"{settings.sub_heartbeat}.resp",
                ),
                "heartbeat",
            )
        )
        task_listener = tg.create_task(
            run_background_task(
                lambda: run_listener(
                    nc,
                    f"{settings.sub_worker_list}.b",
                    f"{settings.sub_worker_list}.l",
                    q_worker_ids,
                ),
                "listener",
            )
        )
        task_workers = tg.create_task(
            run_background_task(
                lambda: run_workers(
                    nc,
                    worker_id,
                    q_worker_ids,
                    f"{settings.sub_veh_deltas}.b",
                    f"{settings.sub_veh_deltas}.l",
                    settings.sub_veh_cmd,
                    settings.sub_veh_status,
                ),
                "workers",
            )
        )
        yield
        task_heartbeat.cancel()
        task_listener.cancel()
        task_workers.cancel()


make_app = make_app_fn(WorkerSettings, _lifespan)
