"""
Champion scoring service — the central runtime for subscriber churn prediction.

Pipeline position:
  After artifacts are validated by RuntimeConfig, this service loads the active
  champion bundle and exposes scoring, calibration, risk-tier assignment, SHAP
  narrative generation, and recommendation logic to API endpoints.

Workflow stage:
  Called by predict.py, subscribers.py, and batch endpoints. Produces CRM-ready
  recommendation rows with raw (uncalibrated) and calibrated probabilities.

Key invariants:
  - Raw scores are for ranking/sorting only; calibrated scores drive business
    thresholds, risk tiers, and CRM decisions.
  - SHAP explanations provide narrative context only — they never select actions.
  - Feature matrix shape must match the runtime feature_columns contract exactly.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.runtime_config import RuntimeConfig, load_runtime_config

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from feature_engineering.builders import build_features
from feature_engineering.constants import CLEANED_INPUT_COLUMNS, VAS_SERVICE_COLUMNS
from modeling.explainability import extract_local_shap_drivers
from modeling.scoring import calibrate_raw_proba as _calibrate_raw_proba
from modeling.scoring import predict_raw_proba as _predict_raw_proba
from preprocessing.config import PERSIAN_MONTH_ORDER
from recommendation.engine import apply_recommendations


class MLService:
    """
    Score subscribers with the active champion bundle and v4 runtime metadata.

    This is the primary entry point for all ML scoring in the backend. It wraps
    the loaded artifacts (model, calibrator, thresholds, feature contract) and
    exposes methods for single/batch scoring, risk tiering, and SHAP narrative
    generation. All scoring flows through this service to guarantee that the
    feature contract, model version, and calibration are consistent.

    References:
      - RuntimeConfig for loaded artifacts
      - score_dataframe / score_feature_dict for batch / single scoring
    """

    def __init__(self) -> None:
        self._runtime: RuntimeConfig | None = None

    @property
    def runtime(self) -> RuntimeConfig:
        if self._runtime is None:
            self._runtime = load_runtime_config()
        return self._runtime

    @property
    def bundle(self) -> dict[str, Any]:
        return self.runtime.champion_bundle

    @property
    def manifest(self) -> dict[str, Any]:
        return self.runtime.champion_manifest

    @property
    def feature_columns(self) -> list[str]:
        return self.runtime.feature_columns

    def predict_raw_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Produce raw (uncalibrated) churn probabilities from the base model.

        The raw score is used for:
          - Ranking subscribers in top-k action queues
          - PR-AUC monitoring and cross-version comparison
          - Priority sorting where relative ordering matters, not absolute risk

        Args:
            X: 2-D feature matrix shaped (n_samples, n_features) matching the
               active feature contract.

        Returns:
            Raw probability estimates (uncalibrated) in [0, 1].

        Raises:
            ValueError: If the feature matrix shape does not match the runtime
                feature_columns contract.

        Why raw vs calibrated:
            The base model's raw scores preserve the relative ranking across
            model versions. Calibrated scores remap values to absolute risk
            levels, which can shift when the calibrator changes. Keeping both
            allows monitoring to distinguish between changes in ranking vs.
            changes in absolute risk calibration.
        """
        self._validate_feature_matrix(X)
        return _predict_raw_proba(self.bundle, X)

    def calibrate_raw_proba(self, p_raw: np.ndarray) -> np.ndarray:
        """
        Map raw probabilities to calibrated churn risk using the artifact calibrator.

        Calibrated probabilities drive:
          - Risk tier assignment (Very High / High / Medium / Low)
          - CRM action selection thresholds
          - Business reporting and executive KPIs

        Args:
            p_raw: Raw probability estimates from predict_raw_proba().

        Returns:
            Calibrated probability estimates in [0, 1].
        """
        return _calibrate_raw_proba(self.bundle, p_raw)

    def assign_risk_tier(self, calibrated_probability: float) -> str:
        """
        Map a calibrated probability to a risk tier string.

        Thresholds are loaded from champion artifacts (risk_band_thresholds)
        and iterated from highest bound to lowest. The cascade ensures the
        highest matching tier is returned.

        Args:
            calibrated_probability: Calibrated churn probability in [0, 1].

        Returns:
            One of the tier labels defined in the champion manifest (e.g.,
            'Very High', 'High', 'Medium', 'Low'). Defaults to 'Low' if no
            threshold is matched.
        """
        thresholds = self.runtime.risk_tier_thresholds
        for tier, bound in sorted(thresholds.items(), key=lambda item: -item[1]):
            if calibrated_probability >= bound:
                return tier
        return "Low"

    def score_features(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Convenience method: produce both raw and calibrated scores in one call.

        Args:
            X: 2-D feature matrix matching the active feature contract.

        Returns:
            Tuple of (raw_probabilities, calibrated_probabilities), each as
            np.ndarray of shape (n_samples,).
        """
        p_raw = self.predict_raw_proba(X)
        p_cal = self.calibrate_raw_proba(p_raw)
        return p_raw, p_cal

    def score_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Score a batch of subscribers and return CRM-ready recommendation rows.

        The input DataFrame may contain either:
          a) The full active feature contract columns (skip feature engineering)
          b) Cleaned subscriber columns consumed by the shared feature-engineering
             package (run build_features to derive the feature vector)

        The output includes the recommendation columns (rule, action, channel,
        priority, etc.) with raw churn probability attached as a rounded column.

        Args:
            df: Subscriber data as a DataFrame (either feature-engineered or
                raw cleaned fields).

        Returns:
            DataFrame with recommendation columns + churn_probability_raw.
        """
        fe = self._feature_frame(df)
        X = self._matrix_from_feature_frame(fe)
        p_raw, p_cal = self.score_features(X)
        rec = apply_recommendations(fe, p_cal, runtime=self.runtime)
        rec["churn_probability_raw"] = np.round(p_raw, 4)
        return rec

    def score_feature_dict(self, features: dict[str, Any]) -> dict[str, Any]:
        """
        Score a single subscriber payload and return CRM-ready metadata dict.

        Accepts either active feature-contract keys or cleaned subscriber fields.
        Coerces the payload into a single-row DataFrame for uniform processing,
        then applies feature engineering if needed.

        Args:
            features: Dictionary of subscriber features (single record).

        Returns:
            Dict with churn_probability_raw, churn_probability, risk_tier,
            and all recommendation fields from apply_recommendations().
            top_driver is resolved via fallback: final_top_driver > rule_top_driver.
        """
        fe = self._feature_frame(pd.DataFrame([self._coerce_single_payload(features)]))
        X = self._matrix_from_feature_frame(fe)
        p_raw, p_cal = self.score_features(X)
        rec = apply_recommendations(fe, p_cal, runtime=self.runtime).iloc[0].to_dict()
        rec["churn_probability_raw"] = float(p_raw[0])
        rec["churn_probability"] = float(p_cal[0])
        rec["risk_tier"] = self.assign_risk_tier(float(p_cal[0]))
        rec.setdefault("top_driver", rec.get("final_top_driver") or rec.get("rule_top_driver"))
        return rec

    def shap_from_vector(self, shap_values: np.ndarray) -> dict[str, Any]:
        """
        Generate narrative SHAP explanations from an artifact-ordered SHAP vector.

        SHAP values are mapped to feature names using the runtime feature_columns,
        and the top-5 positive/negative drivers are extracted along with a natural-
        language summary.

        Args:
            shap_values: 1-D array of SHAP values matching the feature_columns order.

        Returns:
            Dict with:
              - positive_drivers: top-k features pushing risk up
              - negative_drivers: top-k features pushing risk down
              - narrative: human-readable explanation summary

        Why SHAP is narrative-only:
            Per governance policy, SHAP values provide explainability context but
            never drive action selection. Actions are determined by business rules
            in the recommendation engine; SHAP only enriches the CRM display with
            driver-level reasoning.
        """
        detail = extract_local_shap_drivers(shap_values, self.feature_columns, top_k=5)
        return {
            "positive_drivers": detail.get("shap_top_positive", []),
            "negative_drivers": detail.get("shap_top_negative", []),
            "narrative": detail.get("explanation_summary", ""),
        }

    def _validate_feature_matrix(self, X: np.ndarray) -> None:
        if X.ndim != 2:
            raise ValueError("Feature matrix must be 2-dimensional")
        if X.shape[1] != len(self.feature_columns):
            raise ValueError(
                f"Feature matrix has {X.shape[1]} columns; runtime contract expects {len(self.feature_columns)}"
            )

    def _feature_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        if set(self.feature_columns).issubset(df.columns):
            out = df.copy()
            if "subscriber_id" not in out.columns:
                out["subscriber_id"] = np.arange(len(out))
            return out

        missing = [c for c in CLEANED_INPUT_COLUMNS if c not in df.columns]
        if missing:
            df = df.copy()
            for col in missing:
                df[col] = self._default_cleaned_value(col, df)

        return build_features(
            df,
            monthly_spend_q75=float(self.bundle["monthly_spend_q75"]),
            lifetime_arpu_q75=float(self.bundle.get("lifetime_arpu_q75", self.bundle["monthly_spend_q75"])),
        )

    def _matrix_from_feature_frame(self, fe: pd.DataFrame) -> np.ndarray:
        missing = [col for col in self.feature_columns if col not in fe.columns]
        if missing:
            raise ValueError(f"Scoring payload missing active feature columns: {missing}")
        return fe[self.feature_columns].values.astype(np.float64)

    def _coerce_single_payload(self, features: dict[str, Any]) -> dict[str, Any]:
        if set(self.feature_columns).issubset(features.keys()):
            return dict(features)
        return {**{col: self._default_cleaned_value(col, None) for col in CLEANED_INPUT_COLUMNS}, **features}

    def _default_cleaned_value(self, column: str, df: pd.DataFrame | None) -> Any:
        if column == "subscriber_id":
            if df is not None:
                return np.arange(len(df))
            return 0
        if column == "gender":
            return "unknown"
        if column == "age":
            return 0
        if column == "birth_month_persian":
            return next(iter(PERSIAN_MONTH_ORDER))
        if column == "sim_tenure_months":
            return 0.0
        if column == "mobile_data_generation":
            return "4G"
        if column in VAS_SERVICE_COLUMNS or column == "operator_app_usage":
            return "no"
        if column == "sim_card_type":
            return "postpaid"
        if column in ("monthly_spend_toman", "cumulative_spend_toman"):
            return 0.0
        if column in ("churn_binary", "tenure_zero_flag", "billing_definition_ambiguous_flag"):
            return 0
        if column == "is_data_capable":
            return 1
        return None


@lru_cache
def get_ml_service() -> MLService:
    """
    Return a cached singleton MLService instance.

    Cached at the module level so that downstream consumers (endpoints,
    dependency injection) always share the same service, which in turn caches
    the RuntimeConfig artifacts.
    """
    return MLService()
