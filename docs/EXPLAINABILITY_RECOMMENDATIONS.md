# Explainability & Recommendation Layer

## Scope

Connect champion pipeline outputs to **actionable CRM interventions**:

```text
Risk estimation (p_cal) → SHAP explanation (base RF) → business rule → campaign action
```

Not: actions mapped directly from raw features without model risk context.

---

## 1. Global explainability

**Model explained:** tuned `base_model` Random Forest with 47 engineered features.

**Scores:**

| Artifact | Score used |
|----------|------------|
| SHAP values | Raw RF probability link |
| Risk flags in examples | Calibrated `p_cal` |

**Deliverables** (`outputs/explainability/`):

| File | Content |
|------|---------|
| `global_shap_importance.csv` | Mean \|SHAP\|, direction by churner/retainer |
| `shap_beeswarm.png` | Summary beeswarm (test split) |
| `shap_mean_abs_bar.png` | Global importance bar |
| `shap_dependence_*.png` | Dependence plots for top 3 global drivers |
| `subscriber_shap_test.parquet` | Test-split SHAP + scores |
| `subscriber_shap_values.parquet` | **Full population** SHAP for recommendations |
| `explainability_manifest.json` | Drivers, local examples, cautions |

**Expected global leaders:** prepaid, short tenure, prepaid 5G, zero VAS, VoLTE non-adoption, spend ratios.

---

## 2. Local explanations

Per subscriber (population parquet + recommendation merge):

- `shap_top_positive` — risk-increasing drivers
- `shap_top_negative` — risk-decreasing drivers
- `shap_explanation_summary` — business-readable narrative
- `shap_risk_up_drivers` / `shap_risk_down_drivers` — compact labels for BI

Example mapping:

| SHAP feature | Business wording |
|--------------|------------------|
| `early_lifecycle_flag` | New subscriber risk |
| `is_prepaid` + `high_monthly_spend_flag` | High-bill prepaid profile |
| `volte_non_adopter_capable` | Underutilized network capability |

---

## 3. Recommendation engine

**Inputs:**

- `churn_probability` — calibrated (tiers, rules, thresholds)
- `churn_probability_raw` — ranking / top-decile
- Feature flags — rule triggers (prepaid infant, VoLTE, VAS, etc.)
- SHAP — narrative overlay on High / Very High when available

**Rule precedence:** product rules (R00–R13 + R99 — 15 total rule IDs) → fallback save call (R99) → monitor (R00).

**Output:** `outputs/recommendations/subscriber_recommendations.csv`

---

## 4. Risk bands (calibrated probability)

Aligned with champion pipeline / `recommendation.engine.RISK_TIER_THRESHOLDS`:

| Band | Calibrated P(churn) | Urgency | Channel | Offer budget |
|------|---------------------|---------|---------|--------------|
| Very High | ≥ 0.65 | Immediate (48h) | Call + SMS | High (≤ 1× monthly ARPU) |
| High | ≥ 0.30 | 7 days | SMS + optional call | Medium bundle |
| Medium | ≥ 0.15 | 30 days | SMS / app push | Low nudge |
| Low | &lt; 0.15 | Monitor | Quarterly SMS | None |

**Note:** Review examples using 0.70 / 0.45 bands are illustrative; this MVP uses validation-calibrated cutpoints above. Re-tune when prevalence shifts.

---

## Production cautions (documented, not blockers)

1. **Isotonic instability** — ~1,057 validation / ~280 positives; monitor Brier/ECE; consider Platt if distributions drift.
2. **Threshold portability** — operating threshold (e.g. 0.23) is not portable across splits; re-tune on validation each refresh.
3. **RF probability granularity** — scores may cluster; use **raw** score for top-decile / precision@k.

---

## Reproduce

```bash
.venv/bin/python scripts/run_shap_analysis.py
.venv/bin/python scripts/generate_recommendations.py
```

SHAP run exports full-population parquet; recommendations merge it automatically when present.

---

## Downstream (Recommendation Engine / Power BI)

- Sort queue: `campaign_queue_rank`, `churn_probability` (calibrated)
- Rank targeting: `churn_probability_raw` or decile
- Explain panel: `shap_explanation_summary`, `top_driver`
- Filters: `risk_tier`, `rule_id`, `campaign_priority`
