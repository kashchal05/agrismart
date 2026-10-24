"""Unit test for the recommendation serving logic (no network, no real model)."""
import json

import numpy as np
import pytest
import xgboost as xgb

from ml.recommend import predict
from ml.recommend.features import FEATURE_ORDER


@pytest.fixture
def tiny_model(tmp_path, monkeypatch):
    rng = np.random.default_rng(0)
    n, k = 300, len(FEATURE_ORDER)
    X = rng.normal(size=(n, k)).astype("float32")
    # 3 separable classes driven by the first feature.
    y = np.digitize(X[:, 0], [-0.5, 0.5])
    clf = xgb.XGBClassifier(n_estimators=40, max_depth=3, objective="multi:softprob", num_class=3)
    clf.fit(X, y)

    art = tmp_path / "artifacts"
    art.mkdir()
    clf.get_booster().save_model(str(art / "model.json"))
    (art / "meta.json").write_text(json.dumps({
        "feature_order": FEATURE_ORDER,
        "classes": ["Cotton", "Corn", "Sorghum"],
        "trained": "2026-01-01",
    }))
    monkeypatch.setattr(predict, "_ART", art)
    predict.get_recommender.cache_clear()
    return art


def test_recommend_ranks_and_explains(tiny_model):
    rec = predict.get_recommender()
    feats = {f: 0.0 for f in FEATURE_ORDER}
    out = rec.recommend_from_features(feats, top_k=3)

    assert len(out) == 3
    # sorted by suitability descending
    sut = [r["suitability"] for r in out]
    assert sut == sorted(sut, reverse=True)
    # probabilities form a valid distribution over all classes
    assert abs(sum(sut) - 1.0) < 1e-3
    # each recommendation carries up to 3 human-readable reasons
    for r in out:
        assert r["crop"] in {"Cotton", "Corn", "Sorghum"}
        assert 1 <= len(r["why"]) <= 3
        assert r["why"][0]["direction"] in {"favors", "limits"}


def test_missing_model_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(predict, "_ART", tmp_path / "none")
    predict.get_recommender.cache_clear()
    with pytest.raises(predict.ModelNotTrained):
        predict.get_recommender()
