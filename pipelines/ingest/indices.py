"""Pure Sentinel-2 index + cloud-mask math. NumPy in, NumPy out — no network, fully testable.

Reflectance scaling: processing baseline >= 04.00 stores surface reflectance as DN with a BOA
offset of -1000 and scale 1/10000, i.e. reflectance = (DN - 1000) / 10000. The offset matters for
NDVI (it does not cancel in the denominator), so apply it before computing indices.
"""
from __future__ import annotations

import numpy as np

# SCL classes to drop: 0 no-data, 1 saturated, 3 cloud shadow, 8/9 cloud, 10 thin cirrus.
DROP_SCL = (0, 1, 3, 8, 9, 10)

BOA_OFFSET = 1000.0
BOA_SCALE = 10000.0


def to_reflectance(dn: np.ndarray) -> np.ndarray:
    """DN -> surface reflectance in [0, 1]; out-of-range values become NaN."""
    ref = (dn.astype("float32") - BOA_OFFSET) / BOA_SCALE
    return np.where((ref >= 0) & (ref <= 1), ref, np.nan)


def clear_mask(scl: np.ndarray) -> np.ndarray:
    """True where the pixel is a usable (non-cloud/shadow) observation."""
    return ~np.isin(scl, DROP_SCL)


def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    denom = nir + red
    return np.where(denom != 0, (nir - red) / denom, np.nan)


def evi(nir: np.ndarray, red: np.ndarray, blue: np.ndarray) -> np.ndarray:
    denom = nir + 6.0 * red - 7.5 * blue + 1.0
    return np.where(denom != 0, 2.5 * (nir - red) / denom, np.nan)


def ndwi(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """Gao NDWI (vegetation water content): (NIR - SWIR) / (NIR + SWIR)."""
    denom = nir + swir
    return np.where(denom != 0, (nir - swir) / denom, np.nan)


def scene_stats(index_field: np.ndarray, n_field_pixels: int) -> dict[str, float] | None:
    """Mean/percentiles of an index over in-field, cloud-free pixels, plus clear fraction.

    `index_field` is the index array already masked to the field (NaN outside / clouded).
    Returns None if the scene is too clouded to be useful (< 20% of the field visible).
    """
    valid = index_field[~np.isnan(index_field)]
    clear_fraction = len(valid) / n_field_pixels if n_field_pixels else 0.0
    if clear_fraction < 0.20 or valid.size == 0:
        return None
    return {
        "mean": float(np.mean(valid)),
        "p10": float(np.percentile(valid, 10)),
        "p90": float(np.percentile(valid, 90)),
        "clear_fraction": float(clear_fraction),
    }
