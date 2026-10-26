import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    fields: Mapped[list["Field"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Field(Base):
    __tablename__ = "fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # WGS84 polygon of the field boundary, stored as a GeoJSON geometry object.
    # NOTE: JSONB today so the app runs without a local PostGIS build (macOS 14 has no
    # prebuilt PostGIS). On AWS RDS (PostGIS enabled) or a PostGIS-capable local DB, this
    # becomes a real geometry(Polygon,4326) column; see docs/adr/0001-geometry-storage.md.
    geometry: Mapped[dict] = mapped_column(JSONB, nullable=False)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    centroid_lat: Mapped[float] = mapped_column(Float, nullable=False)
    centroid_lon: Mapped[float] = mapped_column(Float, nullable=False)
    county: Mapped[str | None] = mapped_column(String(120), nullable=True)
    county_fips: Mapped[str | None] = mapped_column(String(5), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    owner: Mapped["User"] = relationship(back_populates="fields")
    observations: Mapped[list["FieldObservation"]] = relationship(
        back_populates="field", cascade="all, delete-orphan"
    )


class FieldObservation(Base):
    """One Sentinel-2 satellite observation of a field (per cloud-free solar day)."""

    __tablename__ = "field_observations"
    __table_args__ = (UniqueConstraint("field_id", "scene_date", name="uq_field_scene"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fields.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scene_date: Mapped[date] = mapped_column(Date, nullable=False)
    satellite: Mapped[str] = mapped_column(String(32), default="sentinel-2")
    ndvi_mean: Mapped[float] = mapped_column(Float, nullable=False)
    ndvi_p10: Mapped[float] = mapped_column(Float, nullable=False)
    ndvi_p90: Mapped[float] = mapped_column(Float, nullable=False)
    evi_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    ndwi_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    clear_fraction: Mapped[float] = mapped_column(Float, nullable=False)
    cloud_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    field: Mapped["Field"] = relationship(back_populates="observations")
