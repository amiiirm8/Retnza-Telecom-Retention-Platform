#!/usr/bin/env python3
"""Seed PostgreSQL from current v4 ML/recommendation artifacts."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(REPO_ROOT))

from app.core.config import get_settings
from app.core.runtime_config import load_runtime_config
from app.core.security import hash_password
from app.db.base import Base
from app.models import ChurnPrediction, ModelVersion, Recommendation, ShapExplanation, Subscriber, User
from modeling.explainability import extract_local_shap_drivers

settings = get_settings()


def _clean(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def _bool(value: Any) -> bool | None:
    value = _clean(value)
    if value is None:
        return None
    return bool(value)


def _set_attrs(obj: Any, values: dict[str, Any]) -> Any:
    for key, value in values.items():
        setattr(obj, key, value)
    return obj


def _rec_values(r: pd.Series, runtime: Any) -> dict[str, Any]:
    return {
        "churn_probability": float(r["churn_probability"]),
        "churn_probability_raw": float(r["churn_probability_raw"]),
        "risk_tier": str(r["risk_tier"]),
        "rule_id": str(r["rule_id"]),
        "rule_top_driver": _clean(r.get("rule_top_driver")),
        "shap_top_driver": _clean(r.get("shap_top_driver")),
        "final_top_driver": _clean(r.get("final_top_driver")),
        "final_top_driver_source": _clean(r.get("final_top_driver_source")),
        "top_driver": _clean(r.get("top_driver") or r.get("final_top_driver")),
        "recommended_action": str(r["recommended_action"]),
        "rule_priority": _clean(r.get("rule_priority")),
        "campaign_priority": str(r["campaign_priority"]),
        "campaign_queue_rank": float(r["campaign_queue_rank"]),
        "primary_channel": _clean(r.get("primary_channel")),
        "secondary_channel": _clean(r.get("secondary_channel")),
        "intervention_type": _clean(r.get("intervention_type")),
        "human_touch_flag": bool(r.get("human_touch_flag", False)),
        "digital_only_flag": _bool(r.get("digital_only_flag")),
        "escalation_required": _bool(r.get("escalation_required")),
        "action_assigned": _bool(r.get("action_assigned")),
        "is_fallback_rule": _bool(r.get("is_fallback_rule")),
        "campaign_cost_tier": _clean(r.get("campaign_cost_tier")),
        "offer_budget_numeric_tier": _clean(r.get("offer_budget_numeric_tier")),
        "offer_budget_cap_type": _clean(r.get("offer_budget_cap_type")),
        "campaign_urgency_days": _clean(r.get("campaign_urgency_days")),
        "crm_queue": _clean(r.get("crm_queue")),
        "campaign_channel_group": _clean(r.get("campaign_channel_group")),
        "retention_cost_estimate": _clean(r.get("retention_cost_estimate")),
        "contact_channel": _clean(r.get("contact_channel")),
        "offer_budget": _clean(r.get("offer_budget")),
        "has_rubika": _bool(r.get("has_rubika")),
        "has_ewano": _bool(r.get("has_ewano")),
        "has_hamrahman": _bool(r.get("has_hamrahman")),
        "has_volte": _bool(r.get("has_volte")),
        "ecosystem_product_count": _clean(r.get("ecosystem_product_count")),
        "ecosystem_engagement_level": _clean(r.get("ecosystem_engagement_level")),
        "ecosystem_segment": _clean(r.get("ecosystem_segment")),
        "ecosystem_risk_gap": _bool(r.get("ecosystem_risk_gap")),
        "ecosystem_retention_strategy": _clean(r.get("ecosystem_retention_strategy")),
        "shap_summary": _clean(r.get("shap_explanation_summary")),
        "shap_risk_up_drivers": _clean(r.get("shap_risk_up_drivers")),
        "shap_risk_down_drivers": _clean(r.get("shap_risk_down_drivers")),
        "recommendation_schema_version": runtime.recommendation_schema_version,
        "model_schema_version": runtime.schema_version,
        "feature_contract_version": runtime.feature_schema_version,
    }


async def _upsert_user(db: AsyncSession, email: str, password: str, full_name: str, role: str) -> None:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is None:
        db.add(User(email=email, hashed_password=hash_password(password), full_name=full_name, role=role))


async def seed() -> None:
    runtime = load_runtime_config()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    cleaned = pd.read_parquet(settings.CLEANED_DATA_PATH)
    recs = pd.read_parquet(settings.RECOMMENDATIONS_PATH)
    shap_df = pd.read_parquet(settings.SHAP_PATH) if settings.SHAP_PATH.is_file() else None
    rec_by_sid = {int(r["subscriber_id"]): r for _, r in recs.iterrows()}

    async with Session() as db:
        await _upsert_user(db, "admin@retnza.local", "admin123", "Platform Admin", "admin")
        await _upsert_user(db, "analyst@retnza.local", "analyst123", "Retention Analyst", "user")

        version_tag = runtime.bundle_schema_version or "champion-bundle"
        await db.execute(update(ModelVersion).values(is_active=False))
        mv = await db.scalar(select(ModelVersion).where(ModelVersion.version_tag == version_tag))
        mv_values = {
            "family": runtime.champion_family or "unknown",
            "calibration_method": runtime.calibration_method or "unknown",
            "schema_version": runtime.schema_version,
            "bundle_schema_version": runtime.bundle_schema_version,
            "feature_contract_version": runtime.feature_schema_version,
            "recommendation_schema_version": runtime.recommendation_schema_version,
            "shap_schema_version": runtime.shap_schema_version,
            "compatibility_status": runtime.compatibility_status,
            "is_active": True,
            "test_pr_auc": (runtime.champion_manifest.get("uncalibrated_vs_selected_test") or {}).get(
                "pr_auc_calibrated"
            ),
            "test_brier": (runtime.champion_manifest.get("uncalibrated_vs_selected_test") or {}).get(
                "brier_calibrated"
            ),
            "test_ece": (runtime.champion_manifest.get("uncalibrated_vs_selected_test") or {}).get(
                "ece_calibrated"
            ),
            "operating_threshold": runtime.operating_threshold,
            "metrics_json": json.dumps(runtime.validation),
            "artifact_path": str(settings.CHAMPION_MODEL_PATH),
        }
        if mv is None:
            mv = ModelVersion(version_tag=version_tag, **mv_values)
            db.add(mv)
            await db.flush()
        else:
            _set_attrs(mv, mv_values)
            await db.flush()

        for _, row in cleaned.iterrows():
            sid = int(row["subscriber_id"])
            rec = rec_by_sid.get(sid)
            sub_values = {
                "age": int(row["age"]) if pd.notna(row.get("age")) else None,
                "gender": _clean(row.get("gender")),
                "sim_card_type": _clean(row.get("sim_card_type")),
                "sim_tenure_months": _clean(row.get("sim_tenure_months")),
                "mobile_data_generation": _clean(row.get("mobile_data_generation")),
                "monthly_spend_toman": _clean(row.get("monthly_spend_toman")),
                "cumulative_spend_toman": _clean(row.get("cumulative_spend_toman")),
                "churn_actual": bool(row.get("churn_binary") == 1),
                "is_prepaid": row.get("sim_card_type") == "prepaid",
                "is_data_capable": _bool(row.get("is_data_capable")),
                "has_rubika": _bool(rec.get("has_rubika")) if rec is not None else None,
                "has_ewano": _bool(rec.get("has_ewano")) if rec is not None else None,
                "has_hamrahman": _bool(rec.get("has_hamrahman")) if rec is not None else None,
                "has_volte": _bool(rec.get("has_volte")) if rec is not None else None,
                "ecosystem_product_count": _clean(rec.get("ecosystem_product_count")) if rec is not None else None,
                "ecosystem_engagement_level": _clean(rec.get("ecosystem_engagement_level")) if rec is not None else None,
                "ecosystem_segment": _clean(rec.get("ecosystem_segment")) if rec is not None else None,
                "ecosystem_risk_gap": _bool(rec.get("ecosystem_risk_gap")) if rec is not None else None,
                "ecosystem_retention_strategy": _clean(rec.get("ecosystem_retention_strategy")) if rec is not None else None,
                "attributes_json": row.to_json(force_ascii=False),
            }
            subscriber = await db.get(Subscriber, sid)
            if subscriber is None:
                db.add(Subscriber(id=sid, **sub_values))
            else:
                _set_attrs(subscriber, sub_values)

        await db.flush()

        for _, r in recs.iterrows():
            sid = int(r["subscriber_id"])
            pred = await db.scalar(
                select(ChurnPrediction).where(ChurnPrediction.subscriber_id == sid).limit(1)
            )
            pred_values = {
                "model_version_id": mv.id,
                "churn_probability": float(r["churn_probability"]),
                "churn_probability_raw": float(r["churn_probability_raw"]),
                "risk_tier": str(r["risk_tier"]),
                "champion_family": runtime.champion_family,
                "calibration_method": runtime.calibration_method,
                "model_schema_version": runtime.schema_version,
                "feature_contract_version": runtime.feature_schema_version,
            }
            if pred is None:
                db.add(ChurnPrediction(subscriber_id=sid, **pred_values))
            else:
                _set_attrs(pred, pred_values)

            existing_rec = await db.scalar(
                select(Recommendation).where(Recommendation.subscriber_id == sid).limit(1)
            )
            values = _rec_values(r, runtime)
            if existing_rec is None:
                db.add(Recommendation(subscriber_id=sid, **values))
            else:
                _set_attrs(existing_rec, values)

        if shap_df is not None:
            for _, s in shap_df.iterrows():
                sid = int(s["subscriber_id"])
                shap_vec = [
                    float(s[f"shap_{col}"])
                    for col in runtime.feature_columns
                    if f"shap_{col}" in s.index
                ]
                if len(shap_vec) != len(runtime.feature_columns):
                    continue
                detail = extract_local_shap_drivers(np.array(shap_vec), runtime.feature_columns, top_k=5)
                top_positive = detail.get("shap_top_positive") or []
                top = top_positive[0] if top_positive else {}
                rec = rec_by_sid.get(sid)
                values = {
                    "positive_drivers_json": json.dumps(top_positive),
                    "negative_drivers_json": json.dumps(detail.get("shap_top_negative", [])),
                    "narrative": detail.get("explanation_summary"),
                    "top_feature": top.get("feature"),
                    "top_business_label": top.get("business_label"),
                    "shap_top_driver": _clean(rec.get("shap_top_driver")) if rec is not None else top.get("business_label"),
                    "shap_risk_up_drivers": _clean(rec.get("shap_risk_up_drivers")) if rec is not None else None,
                    "shap_risk_down_drivers": _clean(rec.get("shap_risk_down_drivers")) if rec is not None else None,
                    "shap_schema_version": runtime.shap_schema_version,
                    "feature_contract_version": runtime.feature_schema_version,
                    "top_shap_value": top.get("shap_value"),
                }
                existing_shap = await db.scalar(
                    select(ShapExplanation).where(ShapExplanation.subscriber_id == sid)
                )
                if existing_shap is None:
                    db.add(ShapExplanation(subscriber_id=sid, **values))
                else:
                    _set_attrs(existing_shap, values)

        await db.commit()
    await engine.dispose()
    print("Seed complete: v4 subscribers, recommendations, SHAP, users")


if __name__ == "__main__":
    asyncio.run(seed())
