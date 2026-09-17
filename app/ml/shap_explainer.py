"""Per-request TreeSHAP attribution over the stability surrogate.

Feature-level SHAP values map onto ingredient buckets by role and phase,
anything unattributable lands in a baseline entry so contributions always
reconcile with the model output.
"""

from functools import lru_cache

import numpy as np

from app.ml.predictor import LightGBMPredictor, get_lightgbm_predictor

@lru_cache(maxsize=1)
def get_stability_explainer():
    import shap

    predictor = get_lightgbm_predictor()
    pipeline = predictor._models["stability_pass"]
    booster = pipeline.named_steps["model"].booster_
    return pipeline.named_steps["preprocess"], shap.TreeExplainer(booster)


def explain_stability(features: dict) -> dict[str, float]:
    import pandas as pd

    predictor = get_lightgbm_predictor()
    preprocess, explainer = get_stability_explainer()
    frame = pd.DataFrame([predictor.feature_dict(features)])
    values = np.asarray(explainer.shap_values(preprocess.transform(frame)))[0]
    names = list(preprocess.get_feature_names_out())
    cleaned = [n.split("__")[-1] for n in names]
    return {name: round(float(value), 4) for name, value in zip(cleaned, values)}


def attribute_to_ingredients(
    feature_shap: dict[str, float], buckets: dict[str, list[tuple[str, float]]]
) -> list[dict]:
    attributed: list[dict] = []
    accounted = 0.0
    for feature, members in buckets.items():
        total_weight = sum(weight for _, weight in members)
        for inci, weight in members:
            share = weight / total_weight if total_weight > 0 else 0.0
            value = round(feature_shap.get(feature, 0.0) * share, 4)
            accounted += value
            attributed.append({"label": inci, "shap_value": value})
    remainder = round(sum(feature_shap.values()) - accounted, 4)
    attributed.append({"label": "baseline & process", "shap_value": remainder})
    attributed.sort(key=lambda entry: entry["shap_value"])
    return attributed
