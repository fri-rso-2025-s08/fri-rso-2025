import asyncio
from contextlib import asynccontextmanager, chdir
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi_problem.handler import add_exception_handler

from vehicle_manager.db.core import DatabaseSessionManager
from vehicle_manager.errors import eh
from vehicle_manager.nats import NATS
from vehicle_manager.routes import crud
from vehicle_manager.settings import Settings


def run_migrations(database_url: str):
    with chdir(Path(__file__).parent.parent.parent):
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        alembic_cfg.set_main_option("runningprogrammatically", "1")
        command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def with_session_manager(database_url: str):
    await asyncio.to_thread(run_migrations, database_url)
    dsm = DatabaseSessionManager(database_url)
    try:
        yield dsm
    finally:
        await dsm.close()


@asynccontextmanager
async def with_nats(nats_url):
    nc = NATS()
    while True:
        try:
            await nc.connect(
                nats_url,
                allow_reconnect=True,
                max_reconnect_attempts=-1,
            )
            break
        except Exception:
            await asyncio.sleep(2)
    try:
        yield nc
    finally:
        await nc.close()


def make_app(*, settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()  # type: ignore

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with (
            with_session_manager(settings.database_url) as dsm,
            with_nats(settings.nats_url) as nc,
        ):
            app.state.settings = settings
            app.state.db_session_manager = dsm
            app.state.nc = nc
            add_exception_handler(app, eh)

            app.include_router(
                crud.router,
                prefix=f"/api/vehicle-manager/{settings.tenant_id}",
            )

            yield

    return FastAPI(lifespan=lifespan)
