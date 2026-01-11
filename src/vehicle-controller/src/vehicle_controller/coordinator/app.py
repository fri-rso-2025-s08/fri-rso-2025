import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vehicle_controller.app import make_app_fn
from vehicle_controller.async_value import AsyncValue
from vehicle_controller.coordinator.coordinator import run_coordinator
from vehicle_controller.coordinator.responder import run_responder
from vehicle_controller.coordinator.settings import CoordinatorSettings
from vehicle_controller.nats import get_nats_from_fastapi
from vehicle_controller.resilience import run_background_task
from vehicle_controller.settings import get_settings_from_fastapi


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings_from_fastapi(app, t=CoordinatorSettings)
    nc = await get_nats_from_fastapi(app)
    q_worker_ids = AsyncValue[list[str]]([])

    async with asyncio.TaskGroup() as tg:
        task_coordinator = tg.create_task(
            run_background_task(
                lambda: run_coordinator(
                    nc,
                    f"{settings.sub_heartbeat}.req",
                    f"{settings.sub_heartbeat}.resp",
                    settings.heartbeat_interval,
                    settings.heartbeat_missed_limit,
                    q_worker_ids,
                ),
                "coordinator",
            )
        )
        task_responder = tg.create_task(
            run_background_task(
                lambda: run_responder(
                    nc,
                    q_worker_ids,
                    f"{settings.sub_worker_list}.b",
                    f"{settings.sub_worker_list}.l",
                ),
                "responder",
            )
        )
        yield
        task_coordinator.cancel()
        task_responder.cancel()


make_app = make_app_fn(CoordinatorSettings, _lifespan)
