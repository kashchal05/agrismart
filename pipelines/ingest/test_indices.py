"""Unit tests for the Sentinel-2 index + mask math (no network)."""
import numpy as np

from pipelines.ingest.indices import (
    clear_mask, evi, ndvi, ndwi, scene_stats, to_reflectance,
)


def test_to_reflectance_applies_offset_and_clips():
    dn = np.array([1000, 3000, 11000, 500, 20000], dtype="float32")
    ref = to_reflectance(dn)
    assert ref[0] == 0.0           # (1000-1000)/10000
    assert abs(ref[1] - 0.2) < 1e-6  # (3000-1000)/10000
    assert abs(ref[2] - 1.0) < 1e-6  # (11000-1000)/10000
    assert np.isnan(ref[3])        # negative -> NaN
    assert np.isnan(ref[4])        # > 1 -> NaN


def test_clear_mask_drops_clouds_and_shadows():
    scl = np.array([4, 5, 6, 7, 0, 1, 3, 8, 9, 10])  # veg/soil/water/unclass, then bad classes
    mask = clear_mask(scl)
    assert mask[:4].all()          # 4,5,6,7 kept
    assert not mask[4:].any()      # 0,1,3,8,9,10 dropped


def test_ndvi_healthy_vegetation_is_high():
    nir = np.array([0.4]); red = np.array([0.05])
    assert ndvi(nir, red)[0] > 0.7
    # equal bands -> 0
    assert ndvi(np.array([0.2]), np.array([0.2]))[0] == 0.0


def test_evi_and_ndwi_finite():
    nir, red, blue, swir = (np.array([x]) for x in (0.4, 0.06, 0.02, 0.2))
    assert np.isfinite(evi(nir, red, blue)[0])
    assert np.isfinite(ndwi(nir, swir)[0])


def test_scene_stats_and_cloud_threshold():
    field = np.full(100, 0.5)        # 100 in-field pixels, all clear
    s = scene_stats(field, 100)
    assert s["mean"] == 0.5 and s["clear_fraction"] == 1.0

    mostly_clouded = np.full(100, np.nan)
    mostly_clouded[:10] = 0.5        # only 10% visible -> below 20% floor
    assert scene_stats(mostly_clouded, 100) is None
