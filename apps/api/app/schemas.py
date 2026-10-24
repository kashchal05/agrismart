import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field as PydField, field_validator


# ---- auth ----
class UserCreate(BaseModel):
    email: EmailStr
    password: str = PydField(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- geometry ----
class PolygonGeometry(BaseModel):
    """A GeoJSON Polygon (the only geometry type we accept for a field)."""

    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]

    @field_validator("coordinates")
    @classmethod
    def _non_trivial_ring(cls, v: list[list[list[float]]]) -> list[list[list[float]]]:
        if not v or len(v[0]) < 4:
            raise ValueError("polygon outer ring needs at least 4 positions (closed ring)")
        for lon, lat, *_ in (pt for ring in v for pt in ring):
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError(f"coordinate out of range: ({lon}, {lat})")
        return v


# ---- fields ----
class FieldCreate(BaseModel):
    name: str = PydField(min_length=1, max_length=120)
    geometry: PolygonGeometry


class FieldOut(BaseModel):
    id: uuid.UUID
    name: str
    geometry: dict[str, Any]
    area_ha: float
    centroid_lat: float
    centroid_lon: float
    county: str | None
    county_fips: str | None
    state: str | None
    created_at: datetime
