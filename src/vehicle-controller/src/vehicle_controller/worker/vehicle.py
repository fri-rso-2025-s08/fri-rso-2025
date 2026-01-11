import random
from typing import Any, Literal

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


class VehicleCmdImmobilizer(BaseModel):
    type: Literal["immobilizer"] = "immobilizer"
    active: bool


class VehicleStatusPos(BaseModel):
    type: Literal["pos"] = "pos"
    lat: float
    lon: float


class VehicleStatusImmobilizer(BaseModel):
    type: Literal["immobilizer"] = "immobilizer"
    active: bool


VehicleStatus = VehicleStatusPos | VehicleStatusImmobilizer
VehicleStatusAdapter = TypeAdapter[VehicleStatus](VehicleStatus)


async def run_vehicle_controller(
    nc: NATS,
    vehicle_config: VehicleConfig,
    sub_veh_cmd: str,
    sub_veh_status: str,
):
    assert vehicle_config.vtype == "test"  # ran out of time to do this properly
    vdata = _Vdata.model_validate(vehicle_config.vdata)

    async def on_cmd_msg(msg: Msg):
        cmd = VehicleCmdImmobilizer.model_validate_json(msg.data)
        await nc.publish(
            sub_veh_status,
            VehicleStatusImmobilizer(active=cmd.active)
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
                )
                .model_dump_json()
                .encode("utf-8"),
            )
