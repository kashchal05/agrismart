"""Texas agricultural sampling regions and spatial-cell grouping.

We sample inside known cropland regions (not uniformly over Texas, which is mostly rangeland)
so the CDL hit-rate for actual crops is high and the data spans diverse soils/climates.
The spatial *cell* each point falls in is the group used for the spatial holdout, so training
and test areas never overlap.
"""
from __future__ import annotations

import random

# (name, lon_min, lon_max, lat_min, lat_max) — broad TX crop regions.
REGIONS: list[tuple[str, float, float, float, float]] = [
    ("high_plains",      -102.6, -100.6, 33.4, 36.2),  # cotton, corn, wheat, sorghum
    ("rolling_plains",   -100.6,  -98.2, 32.4, 34.6),  # wheat, cotton
    ("blackland_prairie", -97.6,  -96.0, 30.4, 33.6),  # corn, sorghum, cotton, wheat
    ("coastal_bend",      -97.8,  -95.6, 28.0, 30.2),  # cotton, sorghum, corn
    ("rio_grande_valley", -98.6,  -97.4, 26.0, 27.2),  # cotton, sorghum, sugarcane
    ("rice_belt",         -96.6,  -94.6, 29.0, 30.3),  # rice, soybeans
]

CELL_SIZE_DEG = 0.5  # spatial-holdout group resolution (~55 km)


def sample_points(n: int, seed: int = 42) -> list[tuple[float, float]]:
    """Sample n points spread evenly across the crop regions."""
    rng = random.Random(seed)
    pts: list[tuple[float, float]] = []
    per = n // len(REGIONS) + 1
    for _, lo, hi, la, ha in REGIONS:
        for _ in range(per):
            pts.append((rng.uniform(lo, hi), rng.uniform(la, ha)))
    rng.shuffle(pts)
    return pts[:n]


def cell_id(lon: float, lat: float) -> str:
    return f"{int(lon // CELL_SIZE_DEG)}_{int(lat // CELL_SIZE_DEG)}"
