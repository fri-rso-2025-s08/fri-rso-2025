from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from shapely.geometry import shape
from sqlalchemy import select

from vehicle_manager.auth import AUTH_RESPONSES_DICT, GetUserId, get_user_id
from vehicle_manager.controller_link import send_veh_delta, transmit_immobilize
from vehicle_manager.db.core import GetDb
from vehicle_manager.db.models import (
    Geofence,
    GeofenceCreated,
    GeofenceDeleted,
    GeofenceEvent,
    GeofenceModified,
    Vehicle,
    VehicleCreated,
    VehicleDeleted,
    VehicleEvent,
    VehicleGeofence,
    VehicleGeofenceEvent,
    VehicleImmobilized,
    VehicleModified,
    VehiclePos,
)
from vehicle_manager.errors import GeofenceNotFoundError, VehicleNotFoundError, eh
from vehicle_manager.nats import GetNats
from vehicle_manager.settings import GetSettings


def todo(reason: str):
    raise RuntimeError(f"TODO: {reason}")


class VehicleConfigTest(BaseModel):
    lat: float
    lon: float
    std: float


class VehicleBase(BaseModel):
    name: str = Field(max_length=64)
    vtype: Literal["test"]
    vconfig: VehicleConfigTest


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    name: str | None = Field(None, max_length=64)
    immobilized: bool | None = None


class VehicleRead(VehicleBase):
    id: UUID
    active: bool
    immobilized: bool
    lat: float | None
    lon: float | None

    model_config = {"from_attributes": True}


class GeofenceBase(BaseModel):
    name: str = Field(max_length=64)
    data: dict[str, Any]  # GeoJSON
    immobilize_enter: bool
    immobilize_leave: bool

    @field_validator("data")
    @classmethod
    def validate_geojson(cls, v: dict[str, Any]) -> dict[str, Any]:
        try:
            geom = shape(v)
            if not geom.is_valid:
                raise ValueError("Invalid geometry")
        except Exception:
            raise ValueError("Invalid GeoJSON data")
        return v


class GeofenceCreate(GeofenceBase):
    pass


class GeofenceUpdate(BaseModel):
    name: str | None = Field(None, max_length=64)
    immobilize_enter: bool | None = None
    immobilize_leave: bool | None = None


class GeofenceRead(GeofenceBase):
    id: UUID
    active: bool

    model_config = {"from_attributes": True}


class BaseEventRead(BaseModel):
    ts: datetime

    model_config = {"from_attributes": True}


class PosRead(BaseEventRead):
    lat: float
    lon: float


class BaseUserEventRead(BaseEventRead):
    user_id: str


class CreatedEventRead(BaseUserEventRead):
    type: Literal["created"] = "created"


class ModifiedEventRead(BaseUserEventRead):
    type: Literal["modified"] = "modified"


class DeletedEventRead(BaseUserEventRead):
    type: Literal["deleted"] = "deleted"


class ImmobilizedEventRead(BaseEventRead):
    type: Literal["immobilized"] = "immobilized"
    vehicle_id: UUID | None
    user_id: str | None
    geofence_id: UUID | None
    immobilized: bool


class GeofenceEventRead(BaseEventRead):
    type: Literal["geofence"] = "geofence"
    geofence_id: UUID | None
    entered: bool


router = APIRouter(
    dependencies=[Depends(get_user_id)],
    responses=AUTH_RESPONSES_DICT,
)


VEH_RESPONSES_DICT: dict[str | int, Any] = {
    404: eh.generate_swagger_response(VehicleNotFoundError)
}
GEO_RESPONSES_DICT: dict[str | int, Any] = {
    404: eh.generate_swagger_response(GeofenceNotFoundError)
}
BOTH_RESPONSES_DICT: dict[str | int, Any] = {
    404: eh.generate_swagger_response(VehicleNotFoundError, GeofenceNotFoundError)
}


@router.get("/vehicles/")
async def list_vehicles(
    db: GetDb,
    active: bool = True,
) -> list[UUID]:
    stmt = select(Vehicle.id).where(Vehicle.active == active)
    result = await db.scalars(stmt)

    return list(result.all())


@router.get("/vehicles/{id}", responses=VEH_RESPONSES_DICT)
async def get_vehicle(
    db: GetDb,
    id: UUID,
) -> VehicleRead:
    vehicle = await db.get(Vehicle, id)
    if not vehicle:
        raise VehicleNotFoundError()

    return VehicleRead.model_validate(vehicle)


@router.post("/vehicles/")
async def create_vehicle(
    db: GetDb,
    nc: GetNats,
    settings: GetSettings,
    user_id: GetUserId,
    payload: VehicleCreate,
) -> VehicleRead:
    ts = datetime.now(UTC)
    vehicle = Vehicle(
        active=True,
        name=payload.name,
        vtype=payload.vtype,
        vconfig=payload.vconfig.model_dump(),
        immobilized=False,
        lat=None,
        lon=None,
    )
    db.add(vehicle)
    await db.flush()

    event = VehicleCreated(ts=ts, vehicle_id=vehicle.id, user_id=user_id)
    db.add(event)

    await send_veh_delta(nc, settings, vehicle)

    return VehicleRead.model_validate(vehicle)


@router.put("/vehicles/{id}", responses=VEH_RESPONSES_DICT)
async def update_vehicle(
    db: GetDb,
    nc: GetNats,
    settings: GetSettings,
    user_id: GetUserId,
    id: UUID,
    payload: VehicleUpdate,
) -> None:
    vehicle = await db.get(Vehicle, id)
    if not vehicle or not vehicle.active:
        raise VehicleNotFoundError()

    modified = False

    if payload.immobilized is not None and payload.immobilized != vehicle.immobilized:
        await transmit_immobilize(nc, settings, id, user_id, None, payload.immobilized)

    if payload.name is not None and payload.name != vehicle.name:
        vehicle.name = payload.name
        modified = True

    if modified:
        mod_event = VehicleModified(
            ts=datetime.now(UTC),
            vehicle_id=vehicle.id,
            user_id=user_id,
        )
        db.add(mod_event)


@router.delete("/vehicles/{id}", responses=VEH_RESPONSES_DICT)
async def delete_vehicle(
    db: GetDb,
    nc: GetNats,
    settings: GetSettings,
    user_id: GetUserId,
    id: UUID,
) -> None:
    vehicle = await db.get(Vehicle, id)
    if not vehicle or not vehicle.active:
        raise VehicleNotFoundError()

    vehicle.active = False
    event = VehicleDeleted(ts=datetime.now(UTC), vehicle_id=vehicle.id, user_id=user_id)
    db.add(event)

    await send_veh_delta(nc, settings, vehicle)


@router.get("/geofences/")
async def list_geofences(
    db: GetDb,
    active: bool = True,
) -> list[UUID]:
    stmt = select(Geofence.id).where(Geofence.active == active)
    result = await db.scalars(stmt)

    return list(result.all())


@router.get("/geofences/{id}", responses=GEO_RESPONSES_DICT)
async def get_geofence(
    db: GetDb,
    id: UUID,
) -> GeofenceRead:
    geofence = await db.get(Geofence, id)
    if not geofence:
        raise GeofenceNotFoundError()

    return GeofenceRead.model_validate(geofence)


@router.post("/geofences/")
async def create_geofence(
    db: GetDb,
    user_id: GetUserId,
    payload: GeofenceCreate,
) -> GeofenceRead:
    ts = datetime.now(UTC)
    geofence = Geofence(
        active=True,
        name=payload.name,
        data=payload.data,
        immobilize_enter=payload.immobilize_enter,
        immobilize_leave=payload.immobilize_leave,
    )
    db.add(geofence)
    await db.flush()

    event = GeofenceCreated(ts=ts, geofence_id=geofence.id, user_id=user_id)
    db.add(event)

    return GeofenceRead.model_validate(geofence)


@router.put("/geofences/{id}", responses=GEO_RESPONSES_DICT)
async def update_geofence(
    db: GetDb,
    user_id: GetUserId,
    id: UUID,
    payload: GeofenceUpdate,
) -> None:
    geofence = await db.get(Geofence, id)
    if not geofence or not geofence.active:
        raise GeofenceNotFoundError()

    modified = False

    if payload.name is not None and payload.name != geofence.name:
        geofence.name = payload.name
        modified = True

    if (
        payload.immobilize_enter is not None
        and payload.immobilize_enter != geofence.immobilize_enter
    ):
        geofence.immobilize_enter = payload.immobilize_enter
        modified = True

    if (
        payload.immobilize_leave is not None
        and payload.immobilize_leave != geofence.immobilize_leave
    ):
        geofence.immobilize_leave = payload.immobilize_leave
        modified = True

    if modified:
        event = GeofenceModified(
            ts=datetime.now(UTC),
            geofence_id=geofence.id,
            user_id=user_id,
        )
        db.add(event)


@router.delete("/geofences/{id}", responses=GEO_RESPONSES_DICT)
async def delete_geofence(
    db: GetDb,
    user_id: GetUserId,
    id: UUID,
) -> None:
    geofence = await db.get(Geofence, id)
    if not geofence or not geofence.active:
        raise GeofenceNotFoundError()

    geofence.active = False
    event = GeofenceDeleted(
        ts=datetime.now(UTC), geofence_id=geofence.id, user_id=user_id
    )
    db.add(event)


@router.get("/geofence_vehicles/{geofence_id}/")
async def list_vehicles_in_geofence_assignment(
    db: GetDb,
    geofence_id: UUID,
) -> list[UUID]:
    stmt = select(VehicleGeofence.vehicle_id).where(
        VehicleGeofence.geofence_id == geofence_id
    )
    result = await db.scalars(stmt)

    return list(result.all())


@router.get("/vehicle_geofences/{vehicle_id}/")
async def list_geofences_assigned_to_vehicle(
    db: GetDb,
    vehicle_id: UUID,
) -> list[UUID]:
    stmt = select(VehicleGeofence.geofence_id).where(
        VehicleGeofence.vehicle_id == vehicle_id
    )
    result = await db.scalars(stmt)

    return list(result.all())


@router.post(
    "/geofence_vehicles/{geofence_id}/{vehicle_id}",
    responses=BOTH_RESPONSES_DICT,
)
async def assign_vehicle_to_geofence(
    db: GetDb,
    geofence_id: UUID,
    vehicle_id: UUID,
) -> None:
    if not await db.scalar(select(Vehicle.active).where(Vehicle.id == vehicle_id)):
        raise VehicleNotFoundError()

    if not await db.scalar(select(Geofence.active).where(Geofence.id == geofence_id)):
        raise GeofenceNotFoundError()

    exists = await db.scalar(
        select(VehicleGeofence)
        .where(VehicleGeofence.vehicle_id == vehicle_id)
        .where(VehicleGeofence.geofence_id == geofence_id)
    )
    if exists:
        return

    assoc = VehicleGeofence(vehicle_id=vehicle_id, geofence_id=geofence_id)
    db.add(assoc)


@router.delete(
    "/geofence_vehicles/{geofence_id}/{vehicle_id}", responses=BOTH_RESPONSES_DICT
)
async def remove_vehicle_from_geofence(
    db: GetDb,
    geofence_id: UUID,
    vehicle_id: UUID,
) -> None:
    stmt = (
        select(VehicleGeofence)
        .where(VehicleGeofence.vehicle_id == vehicle_id)
        .where(VehicleGeofence.geofence_id == geofence_id)
    )
    assoc = await db.scalar(stmt)
    if assoc:
        await db.delete(assoc)


@router.get("/vehicle_positions/{id}")
async def get_vehicle_positions(
    db: GetDb,
    id: UUID,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: Annotated[int, Query(ge=0)] = 0,
) -> list[PosRead]:
    stmt = select(VehiclePos).where(VehiclePos.vehicle_id == id)

    if start_date:
        stmt = stmt.where(VehiclePos.ts >= start_date)
    if end_date:
        stmt = stmt.where(VehiclePos.ts <= end_date)

    stmt = stmt.order_by(VehiclePos.ts.desc())

    if limit > 0:
        stmt = stmt.limit(limit)

    result = await db.scalars(stmt)

    return [PosRead.model_validate(r) for r in result.all()]


# Vibe coding ahead


type EventTypes = (
    CreatedEventRead
    | ModifiedEventRead
    | DeletedEventRead
    | ImmobilizedEventRead
    | GeofenceEventRead
)


@router.get("/vehicle_events/{id}")
async def get_vehicle_events(
    db: GetDb,
    id: UUID,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: Annotated[int, Query(ge=0)] = 0,
) -> list[EventTypes]:
    queries: list[tuple[type[VehicleEvent], type[EventTypes]]] = [
        (VehicleCreated, CreatedEventRead),
        (VehicleDeleted, DeletedEventRead),
        (VehicleModified, ModifiedEventRead),
        (VehicleImmobilized, ImmobilizedEventRead),
        (VehicleGeofenceEvent, GeofenceEventRead),
    ]

    results: list[EventTypes] = []

    for model, schema in queries:
        stmt = select(model).where(model.vehicle_id == id)

        if start_date:
            stmt = stmt.where(model.ts >= start_date)
        if end_date:
            stmt = stmt.where(model.ts <= end_date)

        stmt = stmt.order_by(model.ts.desc())

        if limit > 0:
            stmt = stmt.limit(limit)

        rows = await db.scalars(stmt)
        results += [schema.model_validate(r) for r in rows]

    results.sort(key=lambda x: x.ts, reverse=True)

    if limit > 0:
        return results[:limit]

    return results


@router.get("/geofence_events/{id}")
async def get_geofence_events(
    db: GetDb,
    id: UUID,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: Annotated[int, Query(ge=0)] = 0,
) -> list[EventTypes]:
    queries: list[
        tuple[
            type[GeofenceEvent | VehicleGeofenceEvent | VehicleImmobilized],
            type[EventTypes],
        ]
    ] = [
        (GeofenceCreated, CreatedEventRead),
        (GeofenceDeleted, DeletedEventRead),
        (GeofenceModified, ModifiedEventRead),
        (VehicleImmobilized, ImmobilizedEventRead),
        (VehicleGeofenceEvent, GeofenceEventRead),
    ]

    results: list[EventTypes] = []

    for model, schema in queries:
        stmt = select(model).where(model.geofence_id == id)

        if start_date:
            stmt = stmt.where(model.ts >= start_date)
        if end_date:
            stmt = stmt.where(model.ts <= end_date)

        stmt = stmt.order_by(model.ts.desc())

        if limit > 0:
            stmt = stmt.limit(limit)

        rows = await db.scalars(stmt)
        results += [schema.model_validate(r) for r in rows]

    results.sort(key=lambda x: x.ts, reverse=True)

    if limit > 0:
        return results[:limit]

    return results
