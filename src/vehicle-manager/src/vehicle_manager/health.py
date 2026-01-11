from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from sqlalchemy import text

from vehicle_manager.db.core import DatabaseSessionManager
from vehicle_manager.nats import GetNats

router = APIRouter()


class HealthStatus(BaseModel):
    status: str


@router.get("/live")
async def liveness_probe() -> HealthStatus:
    return HealthStatus(status="alive")


@router.get(
    "/ready",
    response_model=HealthStatus,
    responses={503: {"model": HealthStatus}},
)
async def readiness_probe(request: Request, nc: GetNats):
    healthy = True
    session_maker: DatabaseSessionManager = request.app.state.db_session_manager
    try:
        async with session_maker.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        healthy = False

    if not healthy:
        return Response(
            HealthStatus(status="database unavailable").model_dump_json(),
            status_code=503,
        )

    if not nc.is_connected:
        return Response(
            HealthStatus(status="nats unavailable").model_dump_json(),
            status_code=503,
        )

    return HealthStatus(status="ready")
