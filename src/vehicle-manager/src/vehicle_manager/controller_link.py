import asyncio
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, TypeAdapter
from shapely.geometry import Point, shape
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vehicle_manager.db.core import DatabaseSessionManager
from vehicle_manager.db.models import (
    Geofence,
    Vehicle,
    VehicleGeofence,
    VehicleGeofenceEvent,
    VehicleImmobilized,
    VehiclePos,
)
from vehicle_manager.nats import NATS, Msg, with_cleanup_sub
from vehicle_manager.resilience import with_retries
from vehicle_manager.settings import Settings


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


@with_retries(60, 5.0)
async def transmit_immobilize(
    nc: NATS,
    settings: Settings,
    vehicle_id: UUID,
    user_id: str | None,
    geofence_id: UUID | None,
    active: bool,
):
    await nc.publish(
        f"{settings.sub_veh_cmd}.{vehicle_id}",
        VehicleCmdImmobilizer(
            correlation=VehicleCmdImmobilizerCorrelation(
                user_id=user_id, geofence_id=geofence_id
            ),
            active=active,
        )
        .model_dump_json()
        .encode("utf-8"),
    )


async def process_pos_telemetry(
    db: AsyncSession,
    nc: NATS,
    settings: Settings,
    vehicle_id: UUID,
    lat: float,
    lon: float,
    ts: datetime,
) -> None:
    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle or not vehicle.active:
        return

    prev_pos = (
        (vehicle.lon, vehicle.lat)
        if vehicle.lon is not None and vehicle.lat is not None
        else None
    )

    vehicle.lat = lat
    vehicle.lon = lon
    new_pos = VehiclePos(ts=ts, vehicle_id=vehicle_id, lat=lat, lon=lon)
    db.add(new_pos)

    geofences_stmt = (
        select(Geofence)
        .join(VehicleGeofence, VehicleGeofence.geofence_id == Geofence.id)
        .where(
            and_(VehicleGeofence.vehicle_id == vehicle_id, Geofence.active.is_(True))
        )
    )
    geofences = (await db.scalars(geofences_stmt)).all()

    if not geofences:
        return

    current_point = Point(lon, lat)
    prev_point = Point(*prev_pos) if prev_pos is not None else None

    for gf in geofences:
        try:
            polygon = shape(gf.data)
        except Exception:
            continue

        curr_inside = polygon.contains(current_point)
        prev_inside = polygon.contains(prev_point) if prev_point else False

        if curr_inside != prev_inside:
            db.add(
                VehicleGeofenceEvent(
                    ts=ts,
                    vehicle_id=vehicle_id,
                    geofence_id=gf.id,
                    entered=curr_inside,
                )
            )
            if curr_inside and gf.immobilize_enter and not vehicle.immobilized:
                await transmit_immobilize(nc, settings, vehicle_id, None, gf.id, True)
            if not curr_inside and gf.immobilize_leave and vehicle.immobilized:
                await transmit_immobilize(nc, settings, vehicle_id, None, gf.id, False)


async def process_immobilizer_telemetry(
    db: AsyncSession,
    vehicle_id: UUID,
    correlation: VehicleCmdImmobilizerCorrelation,
    active: bool,
    ts: datetime,
):
    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle or not vehicle.active:
        return

    obj = VehicleImmobilized(
        ts, vehicle_id, correlation.user_id, correlation.geofence_id, active
    )
    db.add(obj)


VehicleStatus = VehicleStatusPos | VehicleStatusImmobilizer
VehicleStatusAdapter = TypeAdapter[VehicleStatus](VehicleStatus)


async def run_telemetry_listener(
    db_session_manager: DatabaseSessionManager,
    nc: NATS,
    settings: Settings,
):
    @with_retries(60, 5.0)
    async def on_status(vehicle_id: UUID, status: VehicleStatus):
        match status:
            case VehicleStatusPos():
                async with db_session_manager.session() as db:
                    await process_pos_telemetry(
                        db,
                        nc,
                        settings,
                        vehicle_id,
                        status.lat,
                        status.lon,
                        status.ts,
                    )
            case VehicleStatusImmobilizer():
                async with db_session_manager.session() as db:
                    await process_immobilizer_telemetry(
                        db,
                        vehicle_id,
                        status.correlation,
                        status.active,
                        status.ts,
                    )

    async def on_msg(msg: Msg):
        vehicle_id = UUID(msg.subject.split(".")[-1])
        status = VehicleStatusAdapter.validate_json(msg.data)
        await on_status(vehicle_id, status)

    async with with_cleanup_sub(
        await nc.subscribe(f"{settings.sub_veh_status}.*", "vm", cb=on_msg)
    ):
        await asyncio.Future()


class VehicleConfig(BaseModel):
    vehicle_id: str
    vtype: str
    vdata: Any


class ResponseUpdate(BaseModel):
    vehicles: list[VehicleConfig]


class ResponseDelete(BaseModel):
    vehicle_ids: list[str]


async def run_veh_listener(
    db_session_manager: DatabaseSessionManager,
    nc: NATS,
    settings: Settings,
):
    async def on_msg(msg: Msg):
        async with db_session_manager.session() as db:
            stmt = select(Vehicle).where(Vehicle.active.is_(True))
            vehicles = [
                VehicleConfig(
                    vehicle_id=str(row.id),
                    vtype=row.vtype,
                    vdata=row.vconfig,
                )
                for row in await db.scalars(stmt)
            ]
            await msg.respond(
                ResponseUpdate(vehicles=vehicles).model_dump_json().encode("utf-8")
            )

    async with with_cleanup_sub(
        await nc.subscribe(f"{settings.sub_veh_deltas}.l", "vm", cb=on_msg)
    ):
        await asyncio.Future()


@with_retries(10, 5.0)
async def send_veh_delta(nc: NATS, settings: Settings, vehicle: Vehicle):
    if vehicle.active:
        resp = ResponseDelete(vehicle_ids=[str(vehicle.id)])
    else:
        resp = ResponseUpdate(
            vehicles=[
                VehicleConfig(
                    vehicle_id=str(vehicle.id),
                    vtype=vehicle.vtype,
                    vdata=vehicle.vconfig,
                )
            ]
        )
    await nc.publish(
        f"{settings.sub_veh_deltas}.b", resp.model_dump_json().encode("utf-8")
    )
