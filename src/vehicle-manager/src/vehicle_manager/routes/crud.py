# ruff: noqa: E712
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from shapely.geometry import Point, shape
from sqlalchemy import select

from vehicle_manager.db.core import GetDb
from vehicle_manager.db.models import (
    Geofence,
    GeofenceCreated,
    GeofenceDeleted,
    GeofenceModified,
    Vehicle,
    VehicleCreated,
    VehicleDeleted,
    VehicleGeofence,
    VehicleGeofenceEvent,
    VehicleImmobilized,
    VehicleModified,
    VehiclePos,
)
from vehicle_manager.errors import VehicleNotFoundError, eh

# ----------------------------------------------------------------------
# Pydantic Schemas
# ----------------------------------------------------------------------


class VehicleCreate(BaseModel):
    user_id: str
    vtype: str
    vconfig: dict[str, Any]


class VehicleUpdate(BaseModel):
    user_id: str
    vtype: str | None = None
    vconfig: dict[str, Any] | None = None


class GeofenceCreate(BaseModel):
    data: dict[str, Any]
    immobilize_enter: bool = False
    immobilize_leave: bool = False


class GeofenceUpdate(BaseModel):
    data: dict[str, Any] | None = None
    immobilize_enter: bool | None = None
    immobilize_leave: bool | None = None


class LatLon(BaseModel):
    lat: float
    lon: float


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def get_utc_now():
    return datetime.now(UTC)


router = APIRouter()

# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.post("/vehicles")
async def create_vehicle(
    payload: VehicleCreate,
    db: GetDb,
) -> str:
    vehicle = Vehicle(
        active=True,
        vtype=payload.vtype,
        vconfig=payload.vconfig,
        immobilized=False,
    )
    db.add(vehicle)
    await db.flush()

    event = VehicleCreated(
        ts=get_utc_now(),
        vehicle_id=vehicle.id,
        user_id=payload.user_id,
    )
    db.add(event)
    await db.commit()

    return str(vehicle.id)


@router.get(
    "/vehicles/{vehicle_id}",
    responses={404: eh.generate_swagger_response(VehicleNotFoundError)},
)
async def get_vehicle(vehicle_id: UUID, db: GetDb):
    stmt = select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.active == True)
    result = await db.execute(stmt)
    vehicle = result.scalar_one_or_none()

    if not vehicle:
        raise VehicleNotFoundError()

    return vehicle


@router.patch(
    "/vehicles/{vehicle_id}",
    responses={404: eh.generate_swagger_response(VehicleNotFoundError)},
)
async def update_vehicle(
    vehicle_id: UUID,
    payload: VehicleUpdate,
    user_id: str,
    db: GetDb,
):
    stmt = select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.active == True)
    result = await db.execute(stmt)
    vehicle = result.scalar_one_or_none()

    if not vehicle:
        raise VehicleNotFoundError()

    if payload.vtype is not None:
        vehicle.vtype = payload.vtype
    if payload.vconfig is not None:
        vehicle.vconfig = payload.vconfig

    event = VehicleModified(ts=get_utc_now(), vehicle_id=vehicle.id, user_id=user_id)
    db.add(event)
    await db.commit()
    return {"status": "updated"}


@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: UUID, user_id: str, db: GetDb):
    stmt = select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.active == True)
    result = await db.execute(stmt)
    vehicle = result.scalar_one_or_none()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    vehicle.active = False

    event = VehicleDeleted(ts=get_utc_now(), vehicle_id=vehicle.id, user_id=user_id)
    db.add(event)
    await db.commit()
    return {"status": "deleted"}


@router.post("/geofences/", response_model=str)
async def create_geofence(
    payload: GeofenceCreate,
    user_id: str,
    db: GetDb,
):
    geo = Geofence(
        active=True,
        data=payload.data,
        immobilize_enter=payload.immobilize_enter,
        immobilize_leave=payload.immobilize_leave,
    )
    db.add(geo)
    await db.flush()

    event = GeofenceCreated(ts=get_utc_now(), geofence_id=geo.id, user_id=user_id)
    db.add(event)
    await db.commit()
    return str(geo.id)


@router.patch("/geofences/{geofence_id}")
async def update_geofence(
    geofence_id: UUID,
    payload: GeofenceUpdate,
    user_id: str,
    db: GetDb,
):
    stmt = select(Geofence).where(Geofence.id == geofence_id, Geofence.active == True)
    result = await db.execute(stmt)
    geo = result.scalar_one_or_none()

    if not geo:
        raise HTTPException(status_code=404, detail="Geofence not found")

    if payload.data is not None:
        geo.data = payload.data
    if payload.immobilize_enter is not None:
        geo.immobilize_enter = payload.immobilize_enter
    if payload.immobilize_leave is not None:
        geo.immobilize_leave = payload.immobilize_leave

    event = GeofenceModified(ts=get_utc_now(), geofence_id=geo.id, user_id=user_id)
    db.add(event)
    await db.commit()
    return {"status": "updated"}


@router.delete("/geofences/{geofence_id}")
async def delete_geofence(
    geofence_id: UUID,
    user_id: str,
    db: GetDb,
):
    stmt = select(Geofence).where(Geofence.id == geofence_id, Geofence.active == True)
    result = await db.execute(stmt)
    geo = result.scalar_one_or_none()

    if not geo:
        raise HTTPException(status_code=404, detail="Geofence not found")

    geo.active = False

    event = GeofenceDeleted(ts=get_utc_now(), geofence_id=geo.id, user_id=user_id)
    db.add(event)
    await db.commit()
    return {"status": "deleted"}


@router.post("/vehicles/{vehicle_id}/position")
async def record_vehicle_position(
    vehicle_id: UUID,
    pos: LatLon,
    db: GetDb,
):
    ts_now = get_utc_now()

    # 1. Fetch Vehicle
    v_result = await db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.active == True)
    )
    vehicle = v_result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # 2. Record Position Event
    pos_event = VehiclePos(ts=ts_now, vehicle_id=vehicle_id, lat=pos.lat, lon=pos.lon)
    db.add(pos_event)

    # 3. Geofence Logic
    # Get geofences linked to this vehicle
    stmt = (
        select(Geofence)
        .join(VehicleGeofence, VehicleGeofence.geofence_id == Geofence.id)
        .where(VehicleGeofence.vehicle_id == vehicle_id)
        .where(Geofence.active == True)
    )
    gf_result = await db.execute(stmt)
    linked_geofences = gf_result.scalars().all()

    current_point = Point(pos.lon, pos.lat)

    for fence in linked_geofences:
        # 3a. Geometry Check
        try:
            # shapely.shape requires the geometry part of the feature
            geom_data = fence.data.get("geometry") or fence.data
            fence_shape = shape(geom_data)
        except Exception:
            # Skip malformed geofences without crashing request
            continue

        is_inside = fence_shape.contains(current_point)

        # 3b. Fetch latest state from DB
        last_evt_stmt = (
            select(VehicleGeofenceEvent)
            .where(VehicleGeofenceEvent.vehicle_id == vehicle_id)
            .where(VehicleGeofenceEvent.geofence_id == fence.id)
            .order_by(VehicleGeofenceEvent.ts.desc())
            .limit(1)
        )
        last_evt_result = await db.execute(last_evt_stmt)
        last_evt = last_evt_result.scalar_one_or_none()

        was_inside = last_evt.entered if last_evt else False

        # 3c. Emit event if state changed
        if is_inside != was_inside:
            gf_event = VehicleGeofenceEvent(
                ts=ts_now,
                vehicle_id=vehicle_id,
                geofence_id=fence.id,
                entered=is_inside,
            )
            db.add(gf_event)

            # 3d. Check Immobilization Logic
            should_immobilize = False
            if is_inside and fence.immobilize_enter:
                should_immobilize = True
            elif not is_inside and fence.immobilize_leave:
                should_immobilize = True

            if should_immobilize and not vehicle.immobilized:
                vehicle.immobilized = True
                imm_event = VehicleImmobilized(
                    ts=ts_now,
                    vehicle_id=vehicle_id,
                    user_id="SYSTEM",
                    geofence_id=fence.id,
                    immobilized=True,
                )
                db.add(imm_event)

    await db.commit()
    return {"status": "position_recorded"}


@router.get("/events/vehicle/{vehicle_id}")
async def list_vehicle_events(vehicle_id: UUID, db: GetDb):
    stmt = (
        select(VehiclePos)
        .where(VehiclePos.vehicle_id == vehicle_id)
        .order_by(VehiclePos.ts.desc())
        .limit(100)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()
    return events
