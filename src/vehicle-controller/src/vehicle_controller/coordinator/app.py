import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vehicle_controller.app import make_app_fn
from vehicle_controller.coordinator.coordinator import run_coordinator
from vehicle_controller.coordinator.settings import CoordinatorSettings
from vehicle_controller.nats import get_nats_from_fastapi
from vehicle_controller.resilience import run_background_task
from vehicle_controller.settings import get_settings_from_fastapi


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings_from_fastapi(app, t=CoordinatorSettings)
    nc = await get_nats_from_fastapi(app)

    async with asyncio.TaskGroup() as tg:
        task_coordinator = tg.create_task(
            run_background_task(
                lambda: run_coordinator(
                    nc,
                    settings.subject_heartbeat + ".req",
                    settings.subject_heartbeat + "resp",
                    settings.heartbeat_interval,
                    settings.heartbeat_missed_limit,
                ),
                "coordinator",
            )
        )
        yield
        task_coordinator.cancel()


make_app = make_app_fn(CoordinatorSettings, _lifespan)
