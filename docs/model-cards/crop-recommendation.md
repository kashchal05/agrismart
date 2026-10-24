# Model Card — Crop Recommendation v1

**Task:** given a field's soil and long-term climate, rank the crops most likely to succeed there.
**Trained:** 2026-10-24 · **Samples:** 1115 · **Crops:** 5 · **Spatial cells:** 118

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
| Top-1 accuracy | **0.413** | 0.127 |
| Top-3 accuracy | **0.880** | — |
| Macro-F1 | **0.377** | — |

Lift over baseline (top-1): **+0.286**.

**Spatial 5-fold CV:** top-1 0.480 ± 0.019, top-3 0.912 ± 0.022.

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
| Cotton | 286 |
| Winter Wheat | 259 |
| Sorghum | 229 |
| Corn | 204 |
| Other Hay/Non Alfalfa | 137 |
