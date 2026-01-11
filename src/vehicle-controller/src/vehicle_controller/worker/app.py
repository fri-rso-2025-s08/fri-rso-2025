import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI

from vehicle_controller.app import make_app_fn
from vehicle_controller.nats import get_nats_from_fastapi
from vehicle_controller.resilience import run_background_task
from vehicle_controller.settings import get_settings_from_fastapi
from vehicle_controller.worker.heartbeat import run_heartbeat
from vehicle_controller.worker.settings import WorkerSettings


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings_from_fastapi(app, t=WorkerSettings)
    nc = await get_nats_from_fastapi(app)
    worker_id = str(uuid4())

    async with asyncio.TaskGroup() as tg:
        task_coordinator = tg.create_task(
            run_background_task(
                lambda: run_heartbeat(
                    nc,
                    worker_id,
                    settings.subject_heartbeat + ".req",
                    settings.subject_heartbeat + "resp",
                ),
                "heartbeat",
            )
        )
        yield
        task_coordinator.cancel()


make_app = make_app_fn(WorkerSettings, _lifespan)
