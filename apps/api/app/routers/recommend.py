"""Crop recommendation endpoint, backed by the trained model in ml/recommend/artifacts.

Feature extraction hits live soil/climate APIs (~3s), so results are cached per field for the
process lifetime. In production this cache moves to the DB / a feature store.
"""
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from ..deps import CurrentUser, DbDep
from ..routers.fields import _owned_field_or_404

# Make the repo-root `ml` package importable from the API service.
_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

router = APIRouter(prefix="/fields", tags=["recommend"])

_cache: dict[uuid.UUID, dict] = {}


@router.get("/{field_id}/recommend")
def recommend(field_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> dict:
    field = _owned_field_or_404(db, current_user.id, field_id)
    if field_id in _cache:
        return _cache[field_id]

    try:
        from ml.recommend.predict import ModelNotTrained, get_recommender
    except Exception as e:  # import-time failure (missing deps)
        raise HTTPException(status_code=500, detail=f"recommender unavailable: {e}")

    try:
        rec = get_recommender()
    except ModelNotTrained:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recommendation model is not trained yet.",
        )

    result = rec.recommend_at(field.centroid_lon, field.centroid_lat)
    result = {"field_id": str(field_id), "field_name": field.name, **result}
    _cache[field_id] = result
    return result
