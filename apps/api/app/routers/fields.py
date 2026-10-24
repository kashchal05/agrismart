import uuid

from fastapi import APIRouter, HTTPException, status
from shapely.geometry import mapping
from sqlalchemy import select

from ..deps import CurrentUser, DbDep
from ..geo import area_hectares, centroid_lonlat, geojson_to_shape, lookup_county
from ..models import Field
from ..schemas import FieldCreate, FieldOut

router = APIRouter(prefix="/fields", tags=["fields"])


def _to_out(field: Field) -> FieldOut:
    return FieldOut(
        id=field.id,
        name=field.name,
        geometry=field.geometry,
        area_ha=field.area_ha,
        centroid_lat=field.centroid_lat,
        centroid_lon=field.centroid_lon,
        county=field.county,
        county_fips=field.county_fips,
        state=field.state,
        created_at=field.created_at,
    )


def _owned_field_or_404(db: DbDep, user_id: uuid.UUID, field_id: uuid.UUID) -> Field:
    # Scope the query to the owner, so one tenant can never touch another's field.
    field = db.scalar(select(Field).where(Field.id == field_id, Field.user_id == user_id))
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    return field


@router.post("", response_model=FieldOut, status_code=status.HTTP_201_CREATED)
def create_field(payload: FieldCreate, db: DbDep, current_user: CurrentUser) -> FieldOut:
    geom = geojson_to_shape(payload.geometry.model_dump())
    if geom.geom_type != "Polygon":
        raise HTTPException(status_code=422, detail="geometry must be a single Polygon")
    lon, lat = centroid_lonlat(geom)
    county = lookup_county(lat, lon)
    field = Field(
        user_id=current_user.id,
        name=payload.name,
        geometry=mapping(geom),  # normalized/closed GeoJSON geometry
        area_ha=round(area_hectares(geom), 4),
        centroid_lat=round(lat, 6),
        centroid_lon=round(lon, 6),
        county=county["county"],
        county_fips=county["county_fips"],
        state=county["state"],
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    return _to_out(field)


@router.get("", response_model=list[FieldOut])
def list_fields(db: DbDep, current_user: CurrentUser) -> list[FieldOut]:
    rows = db.scalars(
        select(Field).where(Field.user_id == current_user.id).order_by(Field.created_at.desc())
    ).all()
    return [_to_out(f) for f in rows]


@router.get("/{field_id}", response_model=FieldOut)
def get_field(field_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> FieldOut:
    return _to_out(_owned_field_or_404(db, current_user.id, field_id))


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_field(field_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> None:
    field = _owned_field_or_404(db, current_user.id, field_id)
    db.delete(field)
    db.commit()
