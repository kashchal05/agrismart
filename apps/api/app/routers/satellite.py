"""Satellite health endpoints: serve a field's NDVI time series, and trigger ingestion.

Ingestion runs the geospatial worker (`pipelines.ingest.run`) as a subprocess using the project's
geospatial venv, so the API itself stays free of the heavy raster stack. In the cloud this same
worker runs on Fargate/Batch, triggered by new-scene SNS events (Phase 4) instead of this endpoint.
"""
import subprocess
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, status
from sqlalchemy import select

from ..config import get_settings
from ..deps import CurrentUser, DbDep
from ..models import FieldObservation
from ..routers.fields import _owned_field_or_404
from ..schemas import ObservationOut

router = APIRouter(prefix="/fields", tags=["satellite"])

_ROOT = Path(__file__).resolve().parents[4]
_WORKER_PY = _ROOT / ".venv" / "bin" / "python"


@router.get("/{field_id}/observations", response_model=list[ObservationOut])
def list_observations(field_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> list:
    _owned_field_or_404(db, current_user.id, field_id)
    rows = db.scalars(
        select(FieldObservation)
        .where(FieldObservation.field_id == field_id)
        .order_by(FieldObservation.scene_date)
    ).all()
    return list(rows)


@router.post("/{field_id}/ingest", status_code=status.HTTP_202_ACCEPTED)
def ingest(field_id: uuid.UUID, db: DbDep, current_user: CurrentUser,
           start: str | None = None, end: str | None = None) -> dict:
    _owned_field_or_404(db, current_user.id, field_id)
    end = end or date.today().isoformat()
    start = start or (date.today() - timedelta(days=430)).isoformat()

    # Fire-and-forget worker; it writes observations idempotently. The UI polls /observations.
    env_db = get_settings().database_url
    subprocess.Popen(
        [str(_WORKER_PY), "-m", "pipelines.ingest.run",
         "--field-id", str(field_id), "--start", start, "--end", end, "--db-url", env_db],
        cwd=str(_ROOT),
    )
    return {"status": "started", "field_id": str(field_id), "start": start, "end": end}
