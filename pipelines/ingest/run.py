"""Backfill / ingest satellite observations for a field into Postgres.

Idempotent: re-running over the same dates updates rows in place (unique on field_id+scene_date),
so a scene can never create duplicate observations — the reliability property Phase 4 depends on.

Usage:
  python -m pipelines.ingest.run --field-id <uuid> --start 2024-04-01 --end 2024-10-31
"""
from __future__ import annotations

import argparse
import os
import uuid

from sqlalchemy import create_engine, text

from pipelines.ingest.process import process_field

DEFAULT_DB = "postgresql+psycopg2://localhost:5432/agrismart"

_UPSERT = text("""
INSERT INTO field_observations
  (id, field_id, scene_date, satellite, ndvi_mean, ndvi_p10, ndvi_p90,
   evi_mean, ndwi_mean, clear_fraction, cloud_pct, created_at)
VALUES
  (:id, :field_id, :scene_date, 'sentinel-2', :ndvi_mean, :ndvi_p10, :ndvi_p90,
   :evi_mean, :ndwi_mean, :clear_fraction, :cloud_pct, now())
ON CONFLICT (field_id, scene_date) DO UPDATE SET
  ndvi_mean = EXCLUDED.ndvi_mean, ndvi_p10 = EXCLUDED.ndvi_p10, ndvi_p90 = EXCLUDED.ndvi_p90,
  evi_mean = EXCLUDED.evi_mean, ndwi_mean = EXCLUDED.ndwi_mean,
  clear_fraction = EXCLUDED.clear_fraction, cloud_pct = EXCLUDED.cloud_pct
""")


def ingest_field(field_id: str, start: str, end: str, db_url: str) -> int:
    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        geom = conn.execute(
            text("SELECT geometry FROM fields WHERE id = :fid"), {"fid": field_id}
        ).scalar()
        if geom is None:
            raise SystemExit(f"field {field_id} not found")

    obs = process_field(geom, start, end)
    if obs:
        with engine.begin() as conn:
            for o in obs:
                conn.execute(_UPSERT, {"id": uuid.uuid4(), "field_id": field_id, **o})
    return len(obs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--field-id", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--db-url", default=os.environ.get("AGRISMART_DATABASE_URL", DEFAULT_DB))
    args = ap.parse_args()
    n = ingest_field(args.field_id, args.start, args.end, args.db_url)
    print(f"ingested {n} observations for field {args.field_id} ({args.start}..{args.end})")


if __name__ == "__main__":
    main()
