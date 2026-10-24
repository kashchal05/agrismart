# ADR 0001 — Field geometry storage: JSONB now, PostGIS on deploy

**Status:** accepted (2026-10-24) · **Phase:** 1 (Module A)

## Context

The build plan calls for storing field boundaries as **PostGIS** polygons in Postgres. On the
local dev machine (macOS 14, Apple Silicon) PostGIS could not be installed without heavy,
approval-gated steps:

- Homebrew no longer ships bottles for macOS 14, so `brew install postgis` compiles from source
  and pulls a dependency that needs a full Xcode.app install.
- No Docker, conda, or Postgres.app present; installing any of them needs explicit user action,
  and the sandbox blocks auto-running downloaded installers.

Module A (field management) does not yet exercise any spatial SQL — no `ST_` queries, no spatial
joins, no nearest-neighbour. Those first appear in Phase 2 (satellite stats) and later (same-crop
neighbour comparisons). So PostGIS is not on Module A's critical path.

## Decision

Store the field boundary as a **GeoJSON geometry in a JSONB column** (`fields.geometry`) on plain
Postgres for local development. Derived values the UI needs now — `area_ha`, `centroid_lat/lon`,
`county/state/county_fips` — are computed in Python at write time (`app/geo.py`: pyproj geodesic
area, shapely centroid, US Census geocoder for county) and stored as columns.

## Upgrade path to PostGIS (Phase 1 deploy / Phase 2)

When running against a PostGIS-capable database (AWS RDS with the PostGIS extension enabled, or a
local PostGIS via conda/Docker/Postgres.app):

1. `CREATE EXTENSION postgis;`
2. Add a `geom geometry(Polygon, 4326)` column with a GiST spatial index.
3. Backfill: `UPDATE fields SET geom = ST_SetSRID(ST_GeomFromGeoJSON(geometry::text), 4326);`
4. Switch the model column to GeoAlchemy2 `Geometry` and read/write via `shape`/`mapping`
   (the git history of `app/models.py` / `app/routers/fields.py` has the exact prior code).
5. Move `area_ha`/`centroid` to `ST_Area(geom::geography)` / `ST_Centroid` if desired.

The API contract (GeoJSON in/out) does not change, so the frontend is unaffected.

## Consequences

- **Good:** app runs and is fully tested today with zero new installs; the API/UI contract matches
  the eventual PostGIS version; the swap is small and localized.
- **Trade-off:** no spatial indexing or spatial SQL locally until PostGIS is present. Acceptable
  because nothing in Phase 1 needs it.
