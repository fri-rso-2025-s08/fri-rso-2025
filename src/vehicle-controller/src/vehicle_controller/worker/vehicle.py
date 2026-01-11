from typing import Any

from pydantic import BaseModel

from vehicle_controller.nats import NATS


class VehicleConfig(BaseModel):
    vehicle_id: str
    vtype: str
    vdata: Any


async def run_vehicle_controller(
    nc: NATS,
    vehicle_config: VehicleConfig,
    sub_veh_cmd: str,
    sub_veh_status: str,
):
    pass
