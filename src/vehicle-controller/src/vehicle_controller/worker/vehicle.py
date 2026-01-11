import asyncio
import random
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, TypeAdapter

from vehicle_controller.nats import NATS, Msg, with_cleanup_sub


class VehicleConfig(BaseModel):
    vehicle_id: str
    vtype: str
    vdata: Any


class _Vdata(BaseModel):
    lat: float
    lon: float
    std: float


class VehicleCmdImmobilizerCorrelation(BaseModel):
    user_id: str | None
    geofence_id: UUID | None


class VehicleCmdImmobilizer(BaseModel):
    type: Literal["immobilizer"] = "immobilizer"
    correlation: VehicleCmdImmobilizerCorrelation
    active: bool


class VehicleStatusPos(BaseModel):
    type: Literal["pos"] = "pos"
    lat: float
    lon: float
    ts: datetime


class VehicleStatusImmobilizer(BaseModel):
    type: Literal["immobilizer"] = "immobilizer"
    correlation: VehicleCmdImmobilizerCorrelation
    active: bool
    ts: datetime


VehicleStatus = VehicleStatusPos | VehicleStatusImmobilizer
VehicleStatusAdapter = TypeAdapter[VehicleStatus](VehicleStatus)


async def run_vehicle_controller(
    nc: NATS,
    vehicle_config: VehicleConfig,
    sub_veh_cmd: str,
    sub_veh_status: str,
):
    # ran out of time to do this properly, vehicle type and behavior is hardcoded
    assert vehicle_config.vtype == "test"
    vdata = _Vdata.model_validate(vehicle_config.vdata)

    async def on_cmd_msg(msg: Msg):
        cmd = VehicleCmdImmobilizer.model_validate_json(msg.data)
        await nc.publish(
            sub_veh_status,
            VehicleStatusImmobilizer(
                correlation=cmd.correlation,
                active=cmd.active,
                ts=datetime.now(UTC),
            )
            .model_dump_json()
            .encode("utf-8"),
        )

    async with with_cleanup_sub(await nc.subscribe(sub_veh_cmd, cb=on_cmd_msg)):
        while True:
            await nc.publish(
                sub_veh_status,
                VehicleStatusPos(
                    lat=vdata.lat + random.gauss(0, vdata.std),
                    lon=vdata.lon + random.gauss(0, vdata.std),
                    ts=datetime.now(UTC),
                )
                .model_dump_json()
                .encode("utf-8"),
            )
            await asyncio.sleep(5.0)
