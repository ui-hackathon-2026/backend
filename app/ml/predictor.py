"""LightGBM surrogate predictor backed by vendored training artifacts.

Each target is a self-contained sklearn Pipeline, imputation included,
so a single feature row is enough for inference. Artifacts live in
app/ml/artifacts and are loaded once per process.
"""

from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

TRAINING_EMPTY_FEATURES_WARNING = "Skipping features without any observed values"

MODEL_FILES = {
    "stability_pass": "target_stability_pass.joblib",
    "phase_separation": "target_phase_separation.joblib",
    "feasible": "target_formulation_feasible.joblib",
    "viscosity": "target_viscosity_cP.joblib",
    "droplet": "target_droplet_size_nm.joblib",
    "pdi": "target_pdi.joblib",
}

DEFAULT_ARTIFACT_DIR = Path(__file__).parent / "artifacts"


def clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, float(value)))


class LightGBMPredictor:
    def __init__(self, model_dir: str | Path | None = None):
        directory = Path(model_dir) if model_dir else DEFAULT_ARTIFACT_DIR
        self._models = {
            name: joblib.load(directory / filename)
            for name, filename in MODEL_FILES.items()
        }

    def feature_row(self, features: dict) -> pd.DataFrame:
        total = (
            features["oil_pct"]
            + features["solvent_pct"]
            + features["emulsifier_pct"]
            + features["humectant_pct"]
            + features["thickener_pct"]
            + features["active_pct"]
            + features["preservative_pct"]
        )
        return pd.DataFrame(
            [
                {
                    "oil_phase_pct": features["oil_pct"],
                    "water_phase_pct": features["solvent_pct"],
                    "emulsifier_pct": features["emulsifier_pct"],
                    "surfactant_pct": 0.0,
                    "humectant_pct": features["humectant_pct"],
                    "thickener_pct": features["thickener_pct"],
                    "active_pct": features["active_pct"],
                    "preservative_pct": features["preservative_pct"],
                    "other_phase_pct": max(0.0, 100.0 - total),
                    "ingredient_count": features["ingredient_count"],
                    "composition_sum_pct": 100.0,
                    "oil_to_emulsifier_ratio": features["oil_pct"]
                    / features["emulsifier_pct"]
                    if features["emulsifier_pct"] > 0
                    else 0.0,
                    "surfactant_to_oil_ratio": features["sor"],
                    "hlb_deviation": features["delta_hlb"],
                    "weighted_molecular_weight": None,
                    "weighted_logp": None,
                    "weighted_tpsa": None,
                    "weighted_hbd": None,
                    "weighted_hba": None,
                    "process_temperature_c": 75.0,
                    "mixing_speed_rpm": 1000.0,
                    "mixing_time_min": 15.0,
                    "homogenization_speed_rpm": 4500.0,
                    "homogenization_time_min": 8.0,
                    "measurement_temperature_c": 25.0,
                    "storage_temperature_c": features["temperature_c"],
                    "storage_duration_days": features["duration_days"],
                    "relative_humidity_pct": 75.0,
                    "shear_rate_s_inv": 10.0,
                    "packaging_type": None,
                    "viscosity_method": "brookfield",
                    "domain": "cosmetic",
                    "product_family": "ow_cream",
                }
            ]
        )

    def predict(self, features: dict) -> dict:
        import warnings

        row = self.feature_row(features)
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=f".*{TRAINING_EMPTY_FEATURES_WARNING}.*",
            )
            proba = {
                name: clamp(self._models[name].predict_proba(row)[0][1], 0.0, 1.0)
                for name in ("stability_pass", "phase_separation", "feasible")
            }
            viscosity = float(self._models["viscosity"].predict(row)[0])
            droplet = float(self._models["droplet"].predict(row)[0])
            pdi = float(self._models["pdi"].predict(row)[0])
        return {
            "stability_score": round(proba["stability_pass"], 3),
            "phase_separation_prob": round(proba["phase_separation"], 3),
            "confidence_score": round(proba["feasible"], 3),
            "dynamic_viscosity_mpas": round(max(0.0, viscosity), 1),
            "mean_droplet_size_nm": round(max(0.0, droplet), 1),
            "polydispersity_index": round(clamp(pdi, 0.0, 1.0), 3),
        }


@lru_cache(maxsize=1)
def get_lightgbm_predictor() -> LightGBMPredictor:
    return LightGBMPredictor()
