"""Feature extraction for crop recommendation: soil (SoilGrids) + climate (NASA POWER).

Deliberately depends only on httpx + numpy + pyproj so the API can import it at serving time
without pulling in the training stack (xgboost/shap/sklearn).

All network calls retry with backoff and raise on persistent failure, so the dataset builder can
decide whether to drop a point.
"""
from __future__ import annotations

import time
from calendar import monthrange

import httpx
from pyproj import Transformer

# ---- endpoints ----
_CDL_URL = "https://nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLValue"
_SOIL_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
_POWER_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"

_to_albers = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)

# SoilGrids properties and depths we pull (one query returns all of them).
_SOIL_PROPS = ["clay", "sand", "silt", "phh2o", "soc", "cec", "bdod", "nitrogen"]
_SOIL_DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]
# Divide SoilGrids mapped integers by these to get interpretable units.
_SOIL_SCALE = {"clay": 10, "sand": 10, "silt": 10, "phh2o": 10, "soc": 10,
               "cec": 10, "bdod": 100, "nitrogen": 100}

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_DAYS = [monthrange(2001, m)[1] for m in range(1, 13)]  # non-leap reference year

# The exact, ordered feature columns the model is trained and served on.
SOIL_FEATURES = [f"{p}_{d}" for p in _SOIL_PROPS for d in ["0_5", "5_15", "15_30"]]
CLIMATE_FEATURES = [
    "precip_annual_mm", "precip_apr_sep_mm", "t2m_annual_c", "t_summer_max_c",
    "t_winter_min_c", "gdd_base10", "frost_free_months",
]
FEATURE_ORDER = SOIL_FEATURES + CLIMATE_FEATURES


def _get(url: str, params: dict, *, timeout: float, retries: int = 4) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = httpx.get(url, params=params, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
            r.raise_for_status()
            return r
        except (httpx.HTTPError,) as e:
            last = e
            time.sleep(min(8.0, 1.5 * (2 ** attempt)))  # backoff
    raise RuntimeError(f"request failed after {retries} tries: {url}") from last


def fetch_cdl(lon: float, lat: float, year: int = 2023) -> int:
    """Return the CDL class code of the crop grown at a point."""
    x, y = _to_albers.transform(lon, lat)
    txt = _get(_CDL_URL, {"year": year, "x": x, "y": y}, timeout=30).text
    # Response embeds a JSON-ish blob: ...value: 2, category: "Cotton"...
    marker = "value: "
    i = txt.find(marker)
    if i == -1:
        raise ValueError(f"no CDL value in response: {txt[:120]}")
    j = txt.find(",", i)
    return int(txt[i + len(marker):j].strip())


def fetch_soil(lon: float, lat: float) -> dict[str, float]:
    params = [("lon", lon), ("lat", lat), ("value", "mean")]
    params += [("property", p) for p in _SOIL_PROPS]
    params += [("depth", d) for d in _SOIL_DEPTHS]
    layers = _get(_SOIL_URL, params, timeout=40).json()["properties"]["layers"]
    out: dict[str, float] = {}
    for layer in layers:
        prop = layer["name"]
        scale = _SOIL_SCALE.get(prop, 1)
        for depth in layer["depths"]:
            label = depth["label"].replace("-", "_").replace("cm", "")  # "0_5"
            val = depth["values"]["mean"]
            out[f"{prop}_{label}"] = float("nan") if val is None else val / scale
    return out


def fetch_climate(lon: float, lat: float) -> dict[str, float]:
    params = {"parameters": "PRECTOTCORR,T2M,T2M_MAX,T2M_MIN", "community": "AG",
              "longitude": lon, "latitude": lat, "format": "JSON"}
    p = _get(_POWER_URL, params, timeout=40).json()["properties"]["parameter"]
    precip_mm = [p["PRECTOTCORR"][m] * d for m, d in zip(_MONTHS, _DAYS)]  # mm/day -> mm/month
    t2m = [p["T2M"][m] for m in _MONTHS]
    tmax = [p["T2M_MAX"][m] for m in _MONTHS]
    tmin = [p["T2M_MIN"][m] for m in _MONTHS]
    gdd = sum(max(t - 10.0, 0.0) * d for t, d in zip(t2m, _DAYS))  # base-10 growing degree days
    return {
        "precip_annual_mm": sum(precip_mm),
        "precip_apr_sep_mm": sum(precip_mm[3:9]),
        "t2m_annual_c": sum(t2m) / 12.0,
        "t_summer_max_c": sum(tmax[5:8]) / 3.0,     # Jun-Aug
        "t_winter_min_c": sum(tmin[11:] + tmin[:2]) / 3.0,  # Dec-Feb
        "gdd_base10": gdd,
        "frost_free_months": float(sum(1 for t in tmin if t > 0.0)),
    }


def build_feature_vector(lon: float, lat: float) -> dict[str, float]:
    """Soil + climate features for a point, keyed by FEATURE_ORDER names."""
    feats = {**fetch_soil(lon, lat), **fetch_climate(lon, lat)}
    return {k: feats.get(k, float("nan")) for k in FEATURE_ORDER}
