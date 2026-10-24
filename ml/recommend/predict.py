"""Load the trained crop-recommendation model and rank crops for a location, with explanations.

Explanations use XGBoost's built-in TreeSHAP (`pred_contribs`) so serving needs only xgboost +
numpy — not the full shap package. Kept importable by the API.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import xgboost as xgb

from ml.recommend.features import build_feature_vector

_ART = Path(__file__).resolve().parent / "artifacts"

# Human-readable labels for the explanation feature names.
FEATURE_LABELS = {
    "precip_annual_mm": "annual rainfall", "precip_apr_sep_mm": "growing-season rainfall",
    "t2m_annual_c": "mean temperature", "t_summer_max_c": "summer heat",
    "t_winter_min_c": "winter cold", "gdd_base10": "growing degree days",
    "frost_free_months": "frost-free months",
}
for _p, _lab in {"clay": "clay", "sand": "sand", "silt": "silt", "phh2o": "soil pH",
                 "soc": "soil organic carbon", "cec": "nutrient capacity (CEC)",
                 "bdod": "bulk density", "nitrogen": "soil nitrogen"}.items():
    for _d, _dl in {"0_5": "topsoil", "5_15": "subsoil", "15_30": "deep soil"}.items():
        FEATURE_LABELS[f"{_p}_{_d}"] = f"{_dl} {_lab}"


class ModelNotTrained(RuntimeError):
    pass


class Recommender:
    def __init__(self) -> None:
        model_path, meta_path = _ART / "model.json", _ART / "meta.json"
        if not model_path.exists() or not meta_path.exists():
            raise ModelNotTrained(f"no trained model in {_ART}; run ml.recommend.train")
        self.meta = json.loads(meta_path.read_text())
        self.classes: list[str] = self.meta["classes"]
        self.features: list[str] = self.meta["feature_order"]
        self.booster = xgb.Booster()
        self.booster.load_model(str(model_path))

    def recommend_from_features(self, feats: dict[str, float], top_k: int = 5) -> list[dict]:
        x = np.array([[feats.get(f, np.nan) for f in self.features]], dtype="float32")
        dm = xgb.DMatrix(x, feature_names=self.features)
        proba = np.asarray(self.booster.predict(dm))[0]
        contribs = np.asarray(self.booster.predict(dm, pred_contribs=True))
        # multiclass -> (1, n_class, n_feat+1); drop the bias column.
        per_class = contribs[0] if contribs.ndim == 3 else contribs.reshape(len(self.classes), -1)[0]

        out = []
        for idx in np.argsort(proba)[::-1][:top_k]:
            c = per_class[idx][:-1]
            top = sorted(zip(self.features, c), key=lambda t: abs(t[1]), reverse=True)[:3]
            why = [
                {"factor": FEATURE_LABELS.get(f, f),
                 "direction": "favors" if v > 0 else "limits",
                 "weight": round(float(abs(v)), 3)}
                for f, v in top
            ]
            out.append({"crop": self.classes[idx], "suitability": round(float(proba[idx]), 4),
                        "why": why})
        return out

    def recommend_at(self, lon: float, lat: float, top_k: int = 5) -> dict:
        feats = build_feature_vector(lon, lat)
        return {"recommendations": self.recommend_from_features(feats, top_k),
                "trained": self.meta.get("trained")}


@lru_cache(maxsize=1)
def get_recommender() -> Recommender:
    return Recommender()
