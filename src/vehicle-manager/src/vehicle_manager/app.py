import asyncio
from contextlib import asynccontextmanager, chdir
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi_problem.handler import add_exception_handler

from vehicle_manager.db.core import DatabaseSessionManager
from vehicle_manager.errors import eh
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


def make_app(*, settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()  # type: ignore

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with with_session_manager(settings.database_url) as dsm:
            app.state.settings = settings
            app.state.db_session_manager = dsm
            add_exception_handler(app, eh)

            yield

    return FastAPI(lifespan=lifespan)
