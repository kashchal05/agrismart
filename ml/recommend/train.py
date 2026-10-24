"""Train the crop-recommendation model with an honest spatial holdout.

- Features: soil (SoilGrids) + climate (NASA POWER). Labels: USDA CDL crop.
- Spatial holdout: whole geographic cells are split train/test (GroupShuffleSplit) so the model is
  never tested on a location near one it trained on. We also run GroupKFold CV for a robust estimate.
- Always compared against a most-frequent-class baseline.
- Reports top-1, top-3 accuracy and macro-F1; saves a SHAP summary; writes a model card.

Usage: python -m ml.recommend.train --data data/recommend/dataset.parquet
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.metrics import f1_score, top_k_accuracy_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.preprocessing import LabelEncoder

from ml.recommend.features import FEATURE_ORDER

ART = Path("ml/recommend/artifacts")
CARD = Path("docs/model-cards/crop-recommendation.md")
MIN_PER_CLASS = 25  # drop crops too rare to learn/evaluate honestly


def _load(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path).dropna(subset=FEATURE_ORDER)
    counts = df["crop"].value_counts()
    keep = counts[counts >= MIN_PER_CLASS].index
    df = df[df["crop"].isin(keep)].reset_index(drop=True)
    return df


def _model(n_classes: int) -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        objective="multi:softprob", num_class=n_classes, tree_method="hist",
        n_estimators=400, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
        reg_lambda=1.0, n_jobs=-1, eval_metric="mlogloss",
    )


def _topk(y_true, proba, labels, k) -> float:
    return top_k_accuracy_score(y_true, proba, k=k, labels=labels)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/recommend/dataset.parquet")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = _load(Path(args.data))
    X = df[FEATURE_ORDER].to_numpy(dtype="float32")
    le = LabelEncoder()
    y = le.fit_transform(df["crop"])
    groups = df["cell"].to_numpy()
    labels = np.arange(len(le.classes_))
    print(f"{len(df)} samples, {len(le.classes_)} crops, {df['cell'].nunique()} spatial cells")

    # ---- spatial holdout: disjoint cells for train/test ----
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=args.seed)
    tr, te = next(gss.split(X, y, groups))
    clf = _model(len(le.classes_)).fit(X[tr], y[tr])
    proba = clf.predict_proba(X[te])
    pred = proba.argmax(1)

    top1 = _topk(y[te], proba, labels, 1)
    top3 = _topk(y[te], proba, labels, 3)
    macro_f1 = f1_score(y[te], pred, average="macro")

    # baseline: always predict the most frequent TRAIN class
    majority = np.bincount(y[tr]).argmax()
    base_top1 = float((y[te] == majority).mean())

    # ---- spatial CV for a robust estimate ----
    n_splits = min(5, df["cell"].nunique())
    gkf = GroupKFold(n_splits=n_splits)
    cv1, cv3 = [], []
    for ctr, cte in gkf.split(X, y, groups):
        m = _model(len(le.classes_)).fit(X[ctr], y[ctr])
        pr = m.predict_proba(X[cte])
        cv1.append(_topk(y[cte], pr, labels, 1))
        cv3.append(_topk(y[cte], pr, labels, 3))

    metrics = {
        "trained": date.today().isoformat(),
        "samples": int(len(df)),
        "n_crops": int(len(le.classes_)),
        "n_cells": int(df["cell"].nunique()),
        "spatial_holdout": {"top1": round(top1, 4), "top3": round(top3, 4),
                            "macro_f1": round(macro_f1, 4)},
        "baseline_most_frequent_top1": round(base_top1, 4),
        "lift_top1_over_baseline": round(top1 - base_top1, 4),
        "spatial_cv": {"top1_mean": round(float(np.mean(cv1)), 4),
                       "top1_std": round(float(np.std(cv1)), 4),
                       "top3_mean": round(float(np.mean(cv3)), 4),
                       "top3_std": round(float(np.std(cv3)), 4),
                       "folds": n_splits},
        "classes": le.classes_.tolist(),
        "class_support": df["crop"].value_counts().to_dict(),
    }
    print(json.dumps(metrics["spatial_holdout"], indent=2))
    print("baseline top1:", base_top1)

    # ---- refit on all data for serving ----
    final = _model(len(le.classes_)).fit(X, y)
    ART.mkdir(parents=True, exist_ok=True)
    final.get_booster().save_model(str(ART / "model.json"))
    (ART / "meta.json").write_text(json.dumps({
        "feature_order": FEATURE_ORDER,
        "classes": le.classes_.tolist(),
        "trained": date.today().isoformat(),
        "metrics": metrics,
    }, indent=2))

    # ---- SHAP summary (on the holdout model); best-effort, never blocks the card ----
    CARD.parent.mkdir(parents=True, exist_ok=True)
    try:
        expl = shap.TreeExplainer(clf)
        sv = expl.shap_values(X[te][:400])
        plt.figure()
        shap.summary_plot(sv, X[te][:400], feature_names=np.array(FEATURE_ORDER),
                          class_names=le.classes_.tolist(), show=False, max_display=12)
        plt.tight_layout()
        plt.savefig(CARD.parent / "crop-recommendation-shap.png", dpi=130, bbox_inches="tight")
    except Exception as e:  # noqa: BLE001
        print(f"[warn] SHAP plot skipped: {e}")

    _write_card(metrics)
    print(f"\nsaved model -> {ART/'model.json'}  and card -> {CARD}")


def _write_card(m: dict) -> None:
    h = m["spatial_holdout"]
    cv = m["spatial_cv"]
    support = "\n".join(f"| {c} | {n} |" for c, n in m["class_support"].items())
    CARD.write_text(f"""# Model Card — Crop Recommendation v1

**Task:** given a field's soil and long-term climate, rank the crops most likely to succeed there.
**Trained:** {m['trained']} · **Samples:** {m['samples']} · **Crops:** {m['n_crops']} · \
**Spatial cells:** {m['n_cells']}

## Data
- **Labels:** USDA Cropland Data Layer (the crop actually grown at each point).
- **Features:** SoilGrids (clay/sand/silt/pH/organic carbon/CEC/bulk density/nitrogen at 3 depths)
  and NASA POWER climate normals (annual & Apr–Sep precip, mean/summer-max/winter-min temperature,
  base-10 growing degree days, frost-free months).
- **Region:** Texas crop regions (High Plains, Rolling Plains, Blackland Prairie, Coastal Bend,
  Rio Grande Valley, Rice Belt).

## Evaluation — spatial holdout (test cells geographically disjoint from training)
| Metric | Model | Baseline (most-frequent) |
|---|---|---|
| Top-1 accuracy | **{h['top1']:.3f}** | {m['baseline_most_frequent_top1']:.3f} |
| Top-3 accuracy | **{h['top3']:.3f}** | — |
| Macro-F1 | **{h['macro_f1']:.3f}** | — |

Lift over baseline (top-1): **{m['lift_top1_over_baseline']:+.3f}**.

**Spatial {cv['folds']}-fold CV:** top-1 {cv['top1_mean']:.3f} ± {cv['top1_std']:.3f}, \
top-3 {cv['top3_mean']:.3f} ± {cv['top3_std']:.3f}.

Feature importance: see `crop-recommendation-shap.png`.

## Honest caveats
- **Spatial holdout only** — no random splits, which would leak nearby pixels and inflate scores.
- CDL labels are per-pixel and noisy at field edges; a point may catch a field margin.
- Class imbalance is real (support below); macro-F1 is the fair headline, not raw accuracy.
- This is a **suitability prior from soil + climate**, not an agronomic yield guarantee. It does not
  know this year's prices, rotations, irrigation, or pests.

## Class support
| Crop | Samples |
|---|---|
{support}
""")


if __name__ == "__main__":
    main()
