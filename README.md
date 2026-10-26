# Agrismart 2.0

> A web platform where a farmer draws their field on a map and gets satellite-based crop health
> monitoring, data-backed crop recommendations, yield forecasts, disease diagnosis from a leaf
> photo, and an AI advisor that answers questions using their own field's data.

Agrismart 2.0 is a ground-up rebuild of the original Agrismart (a PyTorch + Flask crop-prediction
app) into a real production system: live satellite imagery, honest ML evaluation, event-driven
pipelines, and an AWS cloud deployment.

See [`agrismart-2.0-build-plan.md`](agrismart-2.0-build-plan.md) for the full vision, architecture,
and 16-week roadmap.

## Status

**Phase 1 — rebuilt core.** Module A (field management) is built and running locally: sign up, draw
fields on a map, and they persist per-user with computed area, centroid, and county.

| Phase | What | State |
|---|---|---|
| **De-risk** | Satellite NDVI notebook over a Texas field (Earth Search STAC) | **Done** |
| 1 · Module A | Auth + draw/store fields + area/centroid/county (multi-tenant) | **Done** |
| 1 · Module B | Crop recommendation v1 (USDA CDL + soil + climate, XGBoost, spatial holdout) | **Done** |
| 2 · Module C | Satellite health pipeline (Sentinel-2 NDVI) + per-field history + UI chart | **Done (local)** |
| 0 | AWS hygiene, budget alarms, Terraform skeleton, CI | Not started |
| 3 | Crop-type classifier + yield forecaster | Not started |
| 4 | Event-driven alerts | Not started |
| 5 | Disease CV + AI advisor (RAG + agent) | Not started |
| 6 | Hardening + real users | Not started |

## Repository layout

```
apps/        web (React + MapLibre) and api (FastAPI)
pipelines/   ingest (STAC), weather, soil, alerts
ml/          recommend, croptype, yield, disease, common
advisor/     RAG, agent tools, evals
infra/       Terraform (all AWS as code)
notebooks/   exploration / de-risking work
docs/        architecture, model cards, DATA_SOURCES.md
tests/       unit, integration, e2e
```

## Running the app locally (Phase 1 · Module A)

A FastAPI backend ([`apps/api`](apps/api)) and a React + MapLibre frontend ([`apps/web`](apps/web)).
Field boundaries are stored as GeoJSON in Postgres; see
[`docs/adr/0001-geometry-storage.md`](docs/adr/0001-geometry-storage.md) for why JSONB now and the
PostGIS upgrade path for deploy.

**Prerequisites:** Python 3.11, Node 18+, and a local Postgres running on `:5432`.

```bash
# 1. Create the dev + test databases on your local Postgres
./infra/local/db.sh create

# 2. API (http://localhost:8000)
cd apps/api
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload            # auto-creates tables on first run

# 3. Web (http://localhost:5174) — in a second terminal
cd apps/web
npm install
npm run dev
```

Open http://localhost:5174, create an account, click **Draw field**, trace a boundary, and **Finish**.
The field is saved with its area, centroid, and county, and appears on the map.

**Tests** (needs the `agrismart_test` DB from step 1):

```bash
cd apps/api && source .venv/bin/activate && pytest
```

The suite covers auth, field CRUD, geometry/area, and **multi-tenant isolation** (one user can never
see or modify another user's fields).

## Crop recommendation (Phase 1 · Module B)

The rebuilt original model, in [`ml/recommend/`](ml/recommend/). "Draw a field → get ranked crop
suggestions" from that location's soil and long-term climate.

- **Labels:** USDA Cropland Data Layer (the crop actually grown at each sampled point).
- **Features:** SoilGrids (texture, pH, organic carbon, CEC, bulk density, nitrogen at 3 depths) +
  NASA POWER climate normals (rainfall, temperature, growing degree days, frost-free months).
- **Model:** XGBoost multiclass over Texas's major crops, with per-crop SHAP explanations served to
  the UI ("topsoil clay favors this crop").
- **Evaluation — spatial holdout** (test cells geographically disjoint from training, so the model
  isn't graded on places it memorized):

  | Metric | Model | Baseline (most-frequent) |
  |---|---|---|
  | Top-1 accuracy | **0.41** | 0.13 |
  | Top-3 accuracy | **0.88** | — |
  | Spatial 5-fold CV top-1 | **0.48 ± 0.02** | — |

  Full honest write-up (caveats, class support, feature importance) in the
  [model card](docs/model-cards/crop-recommendation.md).

### Reproduce

```bash
cd <repo>
python3.11 -m venv ml/.venv && ml/.venv/bin/pip install -r ml/requirements.txt
ml/.venv/bin/python -m ml.recommend.build_dataset --target 1500   # gathers data from live APIs
ml/.venv/bin/python -m ml.recommend.train                         # writes model + card
```

The trained model is served at `GET /fields/{id}/recommend` and via the **🌱 Recommend crops**
button in the web app.

## Satellite health monitoring (Phase 2 · Module C)

The de-risk notebook, turned into a real pipeline in [`pipelines/ingest/`](pipelines/ingest/).

- **Per-field processing** ([`process.py`](pipelines/ingest/process.py)): STAC search → windowed
  Sentinel-2 COG reads (field pixels only) → SCL cloud/shadow masking → NDVI / EVI / NDWI →
  per-scene field statistics (mean, p10, p90, clear fraction).
- **Storage**: per-field observations in Postgres (`field_observations`), **idempotent** on
  `(field_id, scene_date)` — a scene never produces duplicate rows (the reliability property the
  event-driven Phase 4 depends on).
- **Worker** ([`run.py`](pipelines/ingest/run.py)): backfills a field's history. The same unit runs
  on Fargate/Batch in the cloud, triggered by new-scene SNS events (Phase 4) instead of the CLI.
- **Serving + UI**: `GET /fields/{id}/observations` returns the time series; the web app shows a
  season-long **NDVI chart** (mean line + p10–p90 band) when you click a field, and a
  **Load satellite health** button that triggers ingestion for new fields.
- **Tested**: index + cloud-mask math has unit tests (no network); verified end-to-end — a Texas
  field backfilled 64 cloud-free 2024 scenes, NDVI tracking the full crop cycle (0.17 → 0.48 → down).

**What's deferred to the cloud (Phase 2 deploy / Phase 4):** Step Functions orchestration, Fargate
workers at scale, rendered map tiles to S3, and SNS/SQS event-driven ingestion. The processing
logic is identical — only the trigger and compute substrate change.

```bash
# Backfill a field locally (uses the geospatial venv):
.venv/bin/python -m pipelines.ingest.run --field-id <uuid> --start 2024-04-01 --end 2024-10-31
```

## The de-risk notebook

[`notebooks/01_field_ndvi_timeseries.ipynb`](notebooks/01_field_ndvi_timeseries.ipynb) does the
single biggest de-risking step from the plan (Section 14):

1. Define a Texas field polygon.
2. Search the free [Earth Search STAC API](https://earth-search.aws.element84.com/v1) for
   Sentinel-2 L2A scenes over it.
3. Read only the pixels inside the field (windowed COG reads).
4. Mask clouds/shadows with the scene-classification (SCL) band.
5. Compute NDVI and plot a season-long time series + a map.

### Run it

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-notebook.txt
jupyter lab notebooks/01_field_ndvi_timeseries.ipynb
```

No AWS account or credentials are required — Earth Search Sentinel-2 data is free and read
anonymously.

### Result

Running it over a ~65 ha field near Plainview, TX pulled **62 cloud-masked Sentinel-2 scenes**
across the 2024 season and produced a textbook crop-phenology curve — bare ground in April,
canopy build-up through summer, peak greenness in late September, senescence toward harvest:

![Season NDVI](docs/derisk_ndvi_timeseries.png)

![In-field NDVI map at peak greenness](docs/derisk_ndvi_map.png)

This proves the hardest technical risk (satellite data at scale) end-to-end on free, public data.

## Data sources

All data used is free. License and attribution notes live in
[`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

## License

MIT — see [`LICENSE`](LICENSE).
