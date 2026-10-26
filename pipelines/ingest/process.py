"""Per-field Sentinel-2 processing: STAC search -> windowed COG reads -> masks -> per-scene stats.

This is the reusable unit a Fargate/Batch worker runs per field (Phase 2 cloud). Locally it is
driven by the backfill CLI (`pipelines.ingest.run`) and the API's on-demand ingest.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import odc.stac
import rasterio.features
from pystac_client import Client
from shapely.geometry import mapping, shape

from pipelines.ingest.indices import clear_mask, evi, ndvi, ndwi, scene_stats, to_reflectance

STAC_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-c1-l2a"
BANDS = ["red", "nir", "blue", "swir16", "scl"]


def _field_pixel_mask(ds, geometry) -> np.ndarray:
    gb = ds.odc.geobox
    proj = gpd.GeoSeries([shape(geometry)], crs="EPSG:4326").to_crs(gb.crs)
    return rasterio.features.geometry_mask(
        [mapping(proj.iloc[0])], out_shape=gb.shape, transform=gb.transform, invert=True
    )


def process_field(geometry: dict, start: str, end: str, cloud_lt: int = 70) -> list[dict]:
    """Return one observation dict per usefully-clear scene over [start, end] (YYYY-MM-DD)."""
    client = Client.open(STAC_URL)
    items = list(client.search(
        collections=[COLLECTION], intersects=geometry, datetime=f"{start}/{end}",
        query={"eo:cloud_cover": {"lt": cloud_lt}},
    ).items())
    if not items:
        return []

    cloud_by_day = {}
    for it in items:
        day = it.datetime.date().isoformat()
        cc = it.properties.get("eo:cloud_cover")
        if cc is not None:
            cloud_by_day[day] = min(cloud_by_day.get(day, 100.0), float(cc))

    ds = odc.stac.load(items, bands=BANDS, geopolygon=geometry, resolution=10,
                       groupby="solar_day", chunks={})
    field = _field_pixel_mask(ds, geometry)
    n_field = int(field.sum())
    if n_field == 0:
        return []

    red = to_reflectance(ds["red"].values)
    nir = to_reflectance(ds["nir"].values)
    blue = to_reflectance(ds["blue"].values)
    swir = to_reflectance(ds["swir16"].values)
    scl = ds["scl"].values

    out = []
    for t in range(ds.sizes["time"]):
        keep = clear_mask(scl[t]) & field  # in-field, cloud-free
        nd = np.where(keep, ndvi(nir[t], red[t]), np.nan)
        stats = scene_stats(nd, n_field)
        if stats is None:
            continue
        ev = np.clip(evi(nir[t], red[t], blue[t]), -1, 1)
        nw = ndwi(nir[t], swir[t])
        day = np.datetime_as_string(ds["time"].values[t], unit="D")
        out.append({
            "scene_date": day,
            "cloud_pct": cloud_by_day.get(day),
            "ndvi_mean": stats["mean"], "ndvi_p10": stats["p10"], "ndvi_p90": stats["p90"],
            "evi_mean": float(np.nanmean(np.where(keep, ev, np.nan))),
            "ndwi_mean": float(np.nanmean(np.where(keep, nw, np.nan))),
            "clear_fraction": stats["clear_fraction"],
        })
    out.sort(key=lambda r: r["scene_date"])
    return out
