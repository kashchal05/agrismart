"""Build the crop-recommendation training set from live USDA/soil/climate APIs.

Two phases:
  1. Label a large pool of Texas points with the crop actually grown (CDL) — fast, filter to crops.
  2. For the crop points, fetch soil (SoilGrids) + climate (NASA POWER) features — the slow part.

Resumable: caches CDL labels and the assembled dataset to parquet, so a re-run skips done work.

Usage: python -m ml.recommend.build_dataset --target 1200 --out data/recommend/dataset.parquet
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from ml.recommend.features import FEATURE_ORDER, build_feature_vector, fetch_cdl
from ml.recommend.labels import canonical_code, crop_name, is_crop
from ml.recommend.regions import cell_id, sample_points


def _label_pool(points, workers, cache_path: Path) -> pd.DataFrame:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    done = pd.read_parquet(cache_path) if cache_path.exists() else pd.DataFrame(
        columns=["lon", "lat", "cdl_code"]
    )
    seen = {(round(r.lon, 6), round(r.lat, 6)) for r in done.itertuples()}
    todo = [p for p in points if (round(p[0], 6), round(p[1], 6)) not in seen]
    print(f"CDL: {len(done)} cached, fetching {len(todo)} more")
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_cdl, lon, lat): (lon, lat) for lon, lat in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            lon, lat = futs[fut]
            try:
                rows.append({"lon": lon, "lat": lat, "cdl_code": fut.result()})
            except Exception:
                pass
            if i % 250 == 0:
                pd.concat([done, pd.DataFrame(rows)], ignore_index=True).to_parquet(cache_path)
                print(f"  CDL {i}/{len(todo)}")
    out = pd.concat([done, pd.DataFrame(rows)], ignore_index=True)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(cache_path)
    return out


def _add_features(df: pd.DataFrame, workers: int, out_path: Path) -> pd.DataFrame:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    have = pd.read_parquet(out_path) if out_path.exists() else pd.DataFrame(columns=["lon", "lat"])
    seen = {(round(r.lon, 6), round(r.lat, 6)) for r in have.itertuples()}
    todo = [r for r in df.itertuples() if (round(r.lon, 6), round(r.lat, 6)) not in seen]
    print(f"features: {len(have)} cached, fetching {len(todo)} more")
    rows = list(have.to_dict("records"))

    def work(r):
        feats = build_feature_vector(r.lon, r.lat)
        return {"lon": r.lon, "lat": r.lat, "cell": cell_id(r.lon, r.lat),
                "cdl_code": int(r.cdl_code), "label": canonical_code(int(r.cdl_code)),
                "crop": crop_name(int(r.cdl_code)), **feats}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, r) for r in todo]
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                rows.append(fut.result())
            except Exception:
                pass
            if i % 150 == 0:
                pd.DataFrame(rows).to_parquet(out_path)
                print(f"  features {i}/{len(todo)}")
    out = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_path)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1200, help="crop points to collect features for")
    ap.add_argument("--pool-mult", type=int, default=3, help="candidate pool = target * this")
    ap.add_argument("--out", default="data/recommend/dataset.parquet")
    ap.add_argument("--cdl-workers", type=int, default=10)
    ap.add_argument("--feat-workers", type=int, default=6)
    args = ap.parse_args()

    out_path = Path(args.out)
    cache = out_path.parent / "cdl_cache.parquet"

    pool = sample_points(args.target * args.pool_mult)
    labeled = _label_pool(pool, args.cdl_workers, cache)

    crops = labeled[labeled["cdl_code"].apply(lambda c: is_crop(canonical_code(int(c))))]
    crops = crops.head(args.target)
    print(f"crop points: {len(crops)} / {len(labeled)} labeled "
          f"({100*len(crops)/max(len(labeled),1):.0f}% crop hit-rate)")

    ds = _add_features(crops, args.feat_workers, out_path)
    ds = ds.dropna(subset=FEATURE_ORDER)
    ds.to_parquet(out_path)
    print(f"\nDONE: {len(ds)} usable samples -> {out_path}")
    print(ds["crop"].value_counts().to_string())


if __name__ == "__main__":
    main()
