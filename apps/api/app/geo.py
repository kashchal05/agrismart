"""Geometry helpers: geodesic area, centroid, and county lookup."""

import httpx
from pyproj import Geod
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

_GEOD = Geod(ellps="WGS84")

# US Census geocoder: county from a lon/lat point. Free, no API key.
_CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"


def geojson_to_shape(geometry: dict) -> BaseGeometry:
    geom = shape(geometry)
    if not geom.is_valid:
        geom = geom.buffer(0)  # fix self-intersections / bad winding
    return geom


def area_hectares(geom: BaseGeometry) -> float:
    """Geodesic area on the WGS84 ellipsoid, in hectares."""
    area_m2, _ = _GEOD.geometry_area_perimeter(geom)
    return abs(area_m2) / 10_000.0


def centroid_lonlat(geom: BaseGeometry) -> tuple[float, float]:
    c = geom.centroid
    return c.x, c.y  # (lon, lat)


def lookup_county(lat: float, lon: float, timeout: float = 6.0) -> dict[str, str | None]:
    """Return {county, county_fips, state} for a point, or Nones if lookup fails.

    Best-effort: the app must still work offline, so any error degrades gracefully.
    """
    none = {"county": None, "county_fips": None, "state": None}
    params = {
        "x": lon,
        "y": lat,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "layers": "Counties",
        "format": "json",
    }
    try:
        resp = httpx.get(_CENSUS_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        counties = resp.json().get("result", {}).get("geographies", {}).get("Counties", [])
        if not counties:
            return none
        c = counties[0]
        state_fips = c.get("STATE", "")
        county_fips = c.get("COUNTY", "")
        return {
            # BASENAME is the bare name ("Hale"); NAME includes the suffix ("Hale County").
            "county": c.get("BASENAME") or c.get("NAME"),
            "county_fips": (state_fips + county_fips) or None,
            "state": _STATE_BY_FIPS.get(state_fips),
        }
    except (httpx.HTTPError, ValueError, KeyError):
        return none


_STATE_BY_FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY",
}
