from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, String, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column


class PydanticJSON[T: BaseModel](TypeDecorator):
    impl = JSONB
    cache_ok = True

    def __init__(self, pydantic_model: type[T]):
        super().__init__()
        self.pydantic_model = pydantic_model

    def process_bind_param(self, value: T | None, dialect: Any) -> dict | None:
        return value.model_dump() if value else None

    def process_result_value(self, value: dict | None, dialect: Any) -> T | None:
        return self.pydantic_model.model_validate(value) if value else None


class Base(MappedAsDataclass, DeclarativeBase):
    """Base for all models."""


class Vehicle(Base):
    __tablename__ = "vehicle"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default_factory=uuid4,
        init=False,
    )
    active: Mapped[bool] = mapped_column()
    name: Mapped[str] = mapped_column(String(64))
    vtype: Mapped[str] = mapped_column(String(32))
    vconfig: Mapped[Any] = mapped_column(JSONB)
    immobilized: Mapped[bool] = mapped_column()


class Geofence(Base):
    __tablename__ = "geofence"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default_factory=uuid4,
        init=False,
    )
    active: Mapped[bool] = mapped_column()
    name: Mapped[str] = mapped_column(String(64))
    data: Mapped[Any] = mapped_column(JSONB)
    immobilize_enter: Mapped[bool] = mapped_column()
    immobilize_leave: Mapped[bool] = mapped_column()


class VehicleGeofence(Base):
    __tablename__ = "vehicle_geofence"

    vehicle_id: Mapped[UUID] = mapped_column(ForeignKey(Vehicle.id), primary_key=True)
    geofence_id: Mapped[UUID] = mapped_column(ForeignKey(Geofence.id), primary_key=True)


class EventWithTs(Base):
    __abstract__ = True

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)


class EventWithUser(Base):
    __abstract__ = True

    user_id: Mapped[str] = mapped_column(String(80))


class VehicleEvent(EventWithTs):
    __abstract__ = True

    vehicle_id: Mapped[UUID] = mapped_column(ForeignKey(Vehicle.id), primary_key=True)


class VehiclePos(VehicleEvent):
    __tablename__ = "vehicle_pos"

    lat: Mapped[float] = mapped_column()
    lon: Mapped[float] = mapped_column()


class VehicleCreated(VehicleEvent, EventWithUser):
    __tablename__ = "vehicle_created"


class VehicleDeleted(VehicleEvent, EventWithUser):
    __tablename__ = "vehicle_deleted"


class VehicleModified(VehicleEvent, EventWithUser):
    __tablename__ = "vehicle_modified"


class VehicleImmobilized(VehicleEvent):
    __tablename__ = "vehicle_immobilized"

    user_id: Mapped[str | None] = mapped_column(String(80))
    geofence_id: Mapped[UUID | None] = mapped_column(ForeignKey(Geofence.id))
    immobilized: Mapped[bool] = mapped_column()


class VehicleGeofenceEvent(VehicleEvent):
    __tablename__ = "vehicle_geofence_event"

    geofence_id: Mapped[UUID] = mapped_column(ForeignKey(Geofence.id), primary_key=True)
    entered: Mapped[bool] = mapped_column()


class GeofenceEvent(EventWithTs):
    __abstract__ = True

    geofence_id: Mapped[UUID] = mapped_column(ForeignKey(Geofence.id), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)


class GeofenceCreated(GeofenceEvent, EventWithUser):
    __tablename__ = "geofence_created"


class GeofenceDeleted(GeofenceEvent, EventWithUser):
    __tablename__ = "geofence_deleted"


class GeofenceModified(GeofenceEvent, EventWithUser):
    __tablename__ = "geofence_modified"
