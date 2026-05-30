# Retnza — Telecom Retention Intelligence Platform

## Executive Summary

> *A bilingual (English/Persian) enterprise-grade churn prediction and retention decision-support platform for MCI*
>
> **May 2026**

---

## 1. Problem Statement

Telecom operators lose **20–30% of subscribers annually**. Retention teams need to know **who** is at risk, **why**, and **what to do** — at scale. Existing tools are siloed: model scores without explanation, manual rules, disconnected BI exports, no operational dashboards.

**Retnza solves this** with a single integrated platform answering four questions: who is at risk, why, what to do, and how to act.

---

## 2. Solution Architecture

```
Raw Data → Feature Engineering → Champion Model → SHAP → Business Rules → Dashboard → BI Export
  7,043      47 features         RF (PR-AUC      14 rules           9 pages      CSV/Parquet
  subscribers                     0.657)         0% fallback        bilingual
```

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Dual scores (raw + calibrated) | Raw for ranking, calibrated for CRM decisions |
| Deterministic rules only | ML scores inform; business rules decide actions |
| SHAP is narrative-only | Explains predictions; never overrides rules |
| Bilingual EN/FA | Full Persian support with RTL layout |

---

## 3. Key Findings

### Model Performance (Holdout Test)

| Metric | Value |
|--------|-------|
| **PR-AUC** (uncalibrated) | **0.657** |
| **ROC-AUC** | **0.844** |
| **Brier** (calibrated) | **0.136** |
| **ECE** (calibrated) | **0.025** |
| **Operating Recall** | **86.8%** |
| **Top-decile Lift** | **2.80×** |

### Risk Distribution

| Tier | Threshold | Count | % |
|------|-----------|-------|---|
| Very High | ≥0.65 | 664 | 9.4% |
| High | ≥0.30 | 1,826 | 25.9% |
| Medium | ≥0.15 | 1,664 | 23.6% |
| Low | <0.15 | 2,889 | 41.0% |

### Top Risk Drivers (SHAP)

1. **Prepaid SIM type** — Single strongest risk indicator
2. **Prepaid 5G flag** — Distinct high-risk cluster
3. **Short tenure** — Early-lifecycle = 2.6× higher risk
4. **Low digital engagement** — Weak ecosystem attachment
5. **Bill shock** — Spend spikes vs lifetime average

---

## 4. Behavioral Segmentation

| Segment | Size | Mean Risk | Posture |
|---------|------|-----------|---------|
| **Early-Life At-Risk** | 39.0% | **0.385** ⚠️ | Accelerate onboarding |
| **Premium Digital Engaged** | 37.3% | 0.256 | Loyalty perks |
| **Low-Engagement Stable** | 23.7% | **0.100** ✅ | Standard monitoring |

> **3.8× risk ratio between highest and lowest segment**

---

## 5. Recommendation System

### 14 Deterministic Rules — 0% Fallback Rate

| Top Rules | Coverage | Priority |
|-----------|----------|----------|
| R02: Prepaid 5G | 1,509 (21.4%) | **P1** ⚡ |
| R01: Prepaid Infant | 1,413 (20.1%) | **P1** ⚡ |
| R07: Legacy 2G | 1,101 (15.6%) | P3 |
| R05: Bill Shock | 582 (8.3%) | P2 |
| R00: Monitor Only | 552 (7.8%) | P4 |

### Revenue Projection

| Scenario | Retained | Revenue (Toman) | ROI |
|----------|----------|----------------|-----|
| 🟢 Optimistic | 980 | 574.8M | **75,119%** |
| 🟡 Realistic | 428 | 138.7M | **15,112%** |
| 🔴 Conservative | 160 | 32.4M | **3,385%** |

---

## 6. Platform Screenshots

### Executive Dashboard
![Dashboard](screenshots/dashboard.png)
*Top-level KPIs: 7,043 subscribers, 26.9% mean risk, 2,490 high-risk, 2,962 P1 actions.*

### Behavioral Segmentation
![Behavioral](screenshots/behavioral.png)
*3 K-Means clusters — Early-Life At-Risk (0.385 risk), Premium Digital Engaged (0.256), Low-Engagement Stable (0.100).*

### Model Monitoring & Governance
![Model](screenshots/model.png)
*Champion metrics, threshold policies, artifact freshness, 10-safeguard governance panel.*

### Subscriber Detail with SHAP
![Subscriber](screenshots/subscriber.png)
*Per-subscriber risk score, SHAP drivers, recommendation, ecosystem profile, campaign metadata.*

### Campaign Playbook
![Campaigns](screenshots/campaigns.png)
*Campaign performance metrics, saturation analysis, historical impact projections.*

---

## 7. Governance & Trust

**10-safeguard trust panel** ensures model transparency:

- ✅ Schema compatibility (bundle, SHAP, recommendations)
- ✅ Feature contract validation
- ✅ Artifact freshness tracking
- ✅ Calibration transparency
- ✅ Threshold policy comparison
- ✅ Drift reference availability
- ✅ Stability metrics (CV mean/std)
- ✅ Production tradeoff documentation

> **Wording policy**: All narratives use associative wording. No causal claims. SHAP informs but never overrides business rules.

---

## 8. Limitations (Explicit)

| Area | Limitation |
|------|-----------|
| **Temporal validation** | Single snapshot dataset; no true time-series evaluation |
| **Causal inference** | No uplift modeling; rules are not optimized for treatment effects |
| **Dataset size** | 7K subscribers limits deep subgroup analysis |
| **Redis cache** | Configured but not implemented for dashboard endpoints |
| **CI integration** | Tests exist but not wired into automated CI |
| **Load testing** | No performance tests for dashboard or queue |

---

## 9. Final Verdict

### Strengths

1. **End-to-end ML pipeline** — CSV to dashboard, every stage versioned and tested
2. **Clear ML-to-business separation** — Model scores inform; business rules decide
3. **Strong risk differentiation** — 2.8× top-decile lift, 86.8% recall
4. **Comprehensive explainability** — SHAP global + per-subscriber with causal caveats
5. **Professional bilingual UI** — English and Persian with RTL support
6. **Governance-ready** — 10 safeguards, schema versioning, explicit tradeoffs

### Assessment

> **Stage 4: Cohesive Architecture** — The platform demonstrates clean separation of concerns across 7 pipeline stages, schema-versioned artifacts, comprehensive test coverage (169 frontend tests), bilingual UI, and documented engineering tradeoffs.

### Ready for Deployment

Retnza is ready for live demo:
- 9 operational dashboard pages
- Trained + calibrated churn model
- 14 retention rules with 0% fallback
- 3 interpretable behavioral segments
- Full SHAP explainability
- Governance infrastructure
- BI exports for CRM

---

*Platform version 1.0.0*
