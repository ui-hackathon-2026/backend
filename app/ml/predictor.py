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
        return pd.DataFrame([self.feature_dict(features)])

    def feature_dict(self, features: dict) -> dict:
        total = (
            features["oil_pct"]
            + features["solvent_pct"]
            + features["emulsifier_pct"]
            + features["humectant_pct"]
            + features["thickener_pct"]
            + features["active_pct"]
            + features["preservative_pct"]
        )
        return {
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
            "weighted_descriptor_coverage_pct": None,
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
            "viscosity_change_pct": None,
            "packaging_type": None,
            "viscosity_method": "brookfield",
            "domain": "cosmetic",
            "product_family": "ow_cream",
        }

    def predict(self, features: dict) -> dict:
        return self.predict_many([features])[0]

    def predict_many(
        self, batch: list[dict], only: tuple[str, ...] | None = None
    ) -> list[dict]:
        import warnings

        names = only or tuple(MODEL_FILES)
        frame = pd.DataFrame([self.feature_dict(f) for f in batch])
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=f".*{TRAINING_EMPTY_FEATURES_WARNING}.*",
            )
            proba = {
                name: self._models[name].predict_proba(frame)[:, 1]
                for name in ("stability_pass", "phase_separation", "feasible")
                if name in names
            }
            raw = {
                name: self._models[name].predict(frame)
                for name in ("viscosity", "droplet", "pdi")
                if name in names
            }
        get_p = lambda name: round(clamp(proba[name][i], 0.0, 1.0), 3)
        results = []
        for i in range(len(batch)):
            row = {}
            if "stability_pass" in proba:
                row["stability_score"] = get_p("stability_pass")
            if "phase_separation" in proba:
                row["phase_separation_prob"] = get_p("phase_separation")
            if "feasible" in proba:
                row["confidence_score"] = get_p("feasible")
            if "viscosity" in raw:
                row["dynamic_viscosity_mpas"] = round(max(0.0, float(raw["viscosity"][i])), 1)
            if "droplet" in raw:
                row["mean_droplet_size_nm"] = round(max(0.0, float(raw["droplet"][i])), 1)
            if "pdi" in raw:
                row["polydispersity_index"] = round(clamp(float(raw["pdi"][i]), 0.0, 1.0), 3)
            results.append(row)
        return results


@lru_cache(maxsize=1)
def get_lightgbm_predictor() -> LightGBMPredictor:
    return LightGBMPredictor()
