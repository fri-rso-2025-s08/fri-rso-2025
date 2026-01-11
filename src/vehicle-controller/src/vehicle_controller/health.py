from fastapi import APIRouter, Response
from pydantic import BaseModel

from vehicle_controller.nats import GetNats

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
async def readiness_probe(nc: GetNats):
    if not nc.is_connected:
        return Response(
            HealthStatus(status="nats unavailable").model_dump_json(),
            status_code=503,
        )

    return HealthStatus(status="ready")
