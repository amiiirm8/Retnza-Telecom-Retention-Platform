# Retnza — Telecom Retention Intelligence Platform

## Final Report (English)

> **Version 1.0 — May 2026**

---

## Executive Summary

Retnza is an enterprise-grade telecom churn prediction and retention decision-support platform. It identifies subscribers at risk of churn, explains *why* they are at risk using SHAP driver analysis, recommends *specific* retention actions via 14 deterministic business rules, and delivers insights through an interactive bilingual (English/Persian) dashboard with 9 operational views.

The platform processes **7,043 subscribers** with **47 engineered features** and achieves a **test PR-AUC of 0.657** (uncalibrated) with an **operating recall of 86.8%** at the business-optimized threshold of 0.18. The underlying pipeline spans the full ML lifecycle — from raw CSV cleaning through feature engineering, model selection (Random Forest champion), calibration (Isotonic), explainability (SHAP), behavioral segmentation (K-Means, 3 clusters), and deterministic rule-based retention recommendations (14 rules, 0% fallback rate).

The system is production-architected with a FastAPI/PostgreSQL backend, a Next.js 15 bilingual frontend, Docker Compose deployment, and structured BI exports (CSV/Parquet). It is assessed at **Stage 4: Cohesive Architecture** on the engineering maturity scale.

---

## Problem and Project Objective

### The Telecom Churn Problem

Telecom operators lose 20–30% of subscribers annually. Retention teams face a persistent operational challenge: they need to know **who** is at risk, **why** they are at risk, and **what to do about it** — quickly and at scale. Traditional approaches rely on siloed tools:
- Raw model scores without explanation
- Manual rule writing and spreadsheet-based analysis
- Separate BI exports disconnected from operations
- No bilingual support for diverse stakeholder teams

### Project Objective

Retnza was built to answer four core questions in a single integrated platform:

| Question | How Retnza Answers It |
|----------|----------------------|
| **Who** is at risk? | Churn risk engine scores every subscriber with a calibrated probability. Raw RF score for ranking, isotonic-calibrated for business decisions. |
| **Why** are they at risk? | Per-subscriber SHAP driver analysis identifies the specific signals pushing churn risk up or down. |
| **What** should we do? | Deterministic rule engine (14 rules) maps risk + profile to a specific retention play with channel, offer, and urgency. |
| **How** do we act? | CRM Action Queue, campaign playbook, ecosystem analytics, and structured BI export provide operational surfaces. |

---

## Data Preprocessing Summary

### Raw Data

The dataset (`MCI_Challenge_FinalDataset.csv`, ~1 MB) contains **7,043 subscriber records** with telecom billing, usage, and product information. The historical churn rate is approximately **26.5%**.

### Preprocessing Steps

The preprocessing pipeline (`preprocessing/`) performs:

1. **Column mapping** — Raw CSV columns are mapped to standardized schema
2. **Quality control** — Missing value detection, outlier flagging
3. **Label encoding** — Target variable (`churn_actual`) encoded as binary
4. **Text normalization** — Persian text fields normalized where applicable
5. **Validation** — Schema contract validation against expected types

**Output**: Cleaned parquet at `data/cleaned/` ready for feature engineering.

### Key Notes

- No geographic data exists in the source
- Dataset is a single snapshot (no observation dates)
- All financial values are in Iranian Toman

---

## Exploratory Data Analysis / Key Insights Summary

EDA findings are documented in `docs/EXPLORATORY_ANALYSIS.md` and summarized in the analytics outputs (`outputs/analytics/`). Key insights include:

### Churn Landscape

| Metric | Value |
|--------|-------|
| Base churn probability (mean) | 0.269 |
| Very High risk (≥0.65) | 664 (9.4%) |
| High risk (≥0.30) | 1,826 (25.9%) |
| Medium risk (≥0.15) | 1,664 (23.6%) |
| Low risk (<0.15) | 2,889 (41.0%) |
| High-risk total (Very High + High) | 2,490 (35.4%) |

### Prepaid Volatility

- **Prepaid subscribers** (3,875, 55%) show **mean churn probability of 0.428** vs 0.075 for postpaid — a gap of **0.353** (observed association, not causal)
- Prepaid 5G users are a distinct high-risk cluster

### Tenure as a Risk Factor

- **Early-lifecycle subscribers** (tenure ≤12 months, n=2,186) show **mean risk 0.465** vs 0.181 for tenured subscribers
- Tenure is among the top 3 SHAP drivers

### Ecosystem Effects

- VoLTE adoption associated with **0.137 lower** mean churn probability
- Hamrah Man non-adoption associated with **0.150 higher** mean churn probability
- Legacy voice-only segment: mean risk **0.076** (lowest ecosystem segment)
- Partial ecosystem segment: mean risk **0.365** (highest ecosystem segment)

---

## Feature–Churn Relationship Summary

### Feature Engineering

The feature engineering pipeline (`feature_engineering/`) produces **47 features** across 5 conceptual layers:

| Layer | Description | Example Features |
|-------|-------------|-----------------|
| **Financial** | Spend, ARPU, intensity | `lifetime_arpu_toman`, `log_monthly_spend_toman`, `spend_intensity_score`, `monthly_to_lifetime_arpu_ratio` |
| **Tenure & Lifecycle** | Time-based signals | `sim_tenure_months`, `tenure_bucket`, `early_lifecycle_flag` |
| **Product & Network** | SIM type, network gen, VAS | `is_prepaid`, `mobile_gen_ordinal`, `vas_adoption_count`, `is_data_capable` |
| **Ecosystem & Digital** | App adoption, engagement | `rubika_user_flag`, `ewano_user_flag`, `hamrahman_user_flag`, `digital_engagement_score`, `ecosystem_service_count` |
| **Risk Flags** | Composite business rules | `prepaid_5g_risk_flag`, `prepaid_low_tenure_flag`, `high_value_low_engagement_flag`, `revenue_risk_segment` |

### Top SHAP Drivers

Global SHAP importance identifies these as the strongest predictors:

1. **is_prepaid** — Prepaid SIM type is the single strongest risk indicator
2. **prepaid_5g_risk_flag** — Prepaid on 5G network is a distinct high-risk profile
3. **sim_tenure_months** — Short tenure strongly associates with elevated risk
4. **digital_engagement_score** — Low digital engagement signals higher risk
5. **monthly_to_lifetime_arpu_ratio** — Spend spikes relative to history indicate bill shock risk

> **Note**: SHAP associations are model-derived and associative, not causal. They explain model predictions, not real-world causal mechanisms.

---

## Modeling Summary

### Model Selection Process

Three candidate families were compared using the `simplest_stable_within_pr_auc_tolerance` selection rule:

| Family | Val PR-AUC | Test PR-AUC | Test ROC-AUC | Test Brier | Selected? |
|--------|-----------|-------------|-------------|-----------|-----------|
| **Random Forest** | **0.6211** | **0.6571** | **0.8442** | **0.1589** | **✓ Champion** |
| Logistic Regression | 0.6272 | 0.6583 | 0.8471 | 0.1651 | Tolerated |
| Hist Gradient Boosting | 0.6068 | 0.6055 | 0.8161 | 0.1495 | Below floor |

**Selection rationale**: Random Forest was chosen as the champion because it was the simplest model within the PR-AUC tolerance band (±0.01 absolute, ±2% relative) of the best score, with the highest CV mean PR-AUC (0.6601 ± 0.0192). Preference order: within tolerance → lower fold PR-AUC std → simpler model → lower Brier.

### Champion Model Configuration

```
RandomForestClassifier(
    class_weight='balanced',
    max_depth=10,
    max_features=0.4,
    min_samples_leaf=30,
    n_estimators=500,
    n_jobs=-1,
    random_state=42
)
```

- Hyperparameter tuning: 24 iterations via randomized search
- Best CV PR-AUC: 0.6665

### Calibration

Isotonic calibration was selected over sigmoid and no-calibration options:

| Metric | Uncalibrated | Calibrated (Isotonic) | Improvement |
|--------|-------------|----------------------|-------------|
| PR-AUC | 0.6571 | 0.6334 | -3.6% (expected trade-off) |
| Brier Score | 0.1589 | 0.1363 | **-14.2% ✓** |
| ECE | 0.1344 | 0.0253 | **-81.2% ✓** |

Isotonic calibration significantly improves probability reliability (ECE drops from 0.134 to 0.025) at a small cost in PR-AUC, making the scores suitable for CRM risk band decisions.

### Dual Score Architecture

| Score | Use Case |
|-------|----------|
| `churn_probability_raw` | Ranking, prioritization, top-k, PR-AUC monitoring |
| `churn_probability_calibrated` | Risk bands, CRM thresholds, executive reporting |

### Temporal Stability

The dataset lacks true temporal splits. A tenure-based proxy split (cutoff: 29 months) was used to assess stability:

- Random Forest tenure-proxy PR-AUC: 0.357 (vs validation 0.621)
- The gap reflects the structural difference between tenure-split and stratified-split evaluation, not necessarily model degradation
- Documented limitation: "Dataset has no observation date. Tenure-based split is a weak proxy only"

---

## Model Results / Metrics Summary

### Operating Policy

The **business_min_recall_validation** policy is the recommended operating threshold:

| Threshold Policy | Threshold | Precision | Recall | F1 |
|-----------------|-----------|-----------|--------|-----|
| Default (0.5) | 0.50 | 0.671 | 0.414 | 0.512 |
| **Business min-recall** | **0.18** | **0.463** | **0.868** | **0.604** |
| Max F1 | 0.26 | 0.551 | 0.736 | 0.630 |
| Top Decile | 0.586 | 0.697 | 0.386 | 0.497 |

**Why 0.18?** In telecom retention, a missed churner exits recurring revenue; a false alarm wastes a save offer but retains the subscriber. The min-recall policy prioritizes finding churners (86.8% recall) over avoiding false positives.

### Decile Gains (Top Decile)

| Decile | Churn Rate | Lift |
|--------|-----------|------|
| 1 (top) | 74.3% | 2.80× |
| 2 | 54.7% | 2.07× |
| 3 | 47.2% | 1.78× |
| 4 | 34.3% | 1.29× |
| 5 | 19.8% | 0.75× |

Top-decile concentration is strong: the highest-risk 10% of subscribers capture 74.3% actual churn rate (2.8× base rate).

### Full Holdout Test Results (at operating threshold)

| Metric | Value |
|--------|-------|
| PR-AUC (calibrated) | 0.633 |
| ROC-AUC | 0.843 |
| Brier Score | 0.136 |
| ECE | 0.025 |
| Precision | 0.463 |
| Recall | 0.868 |
| F1 Score | 0.604 |
| False Negative Rate | 0.132 |
| Lift | 1.75× |

---

## Explainability Summary

### SHAP Analysis

SHAP (SHapley Additive exPlanations) values are computed on the base Random Forest model (before calibration) for narrative overlay. Key design decisions:

- **SHAP does NOT select actions** — all recommendations are rule-driven; SHAP is narrative-only
- **SHAP explains the base model**, not the calibrated score (calibration is monotonic and not explained)
- **SHAP overlays** enrich the subscriber detail view for CRM agents with risk driver narratives

### Global SHAP Importance

![SHAP Global Importance](screenshots/evidence.png)
*Figure 1: Evidence & Insights page showing SHAP global importance, rule diagnostics, and explainability artifacts. The page aggregates model-wide SHAP drivers and rule performance metrics.*

### Per-Subscriber SHAP

The subscriber detail page shows per-subscriber SHAP drivers (positive and negative) alongside the recommendation. This helps CRM agents understand *why* a specific subscriber is flagged and *what* the primary risk drivers are.

### SHAP Interaction Analysis

The analytics module (`analytics/shap_interactions.py`) computes top SHAP interaction pairs, identifying features that most strongly modulate each other's impact on predictions. Results are saved to `outputs/analytics/shap_interaction_top_pairs.parquet`.

---

## Recommendation Engine Summary

### Architecture

The recommendation engine (`recommendation/`) is a **deterministic rule-based system** — not an ML model. Key principles:

1. **Rules are pure functions** of subscriber features
2. **Precedence-ordered matching** — highest-priority rule that fires wins
3. **SHAP never selects actions** — rules determine `rule_id` and `recommended_action`
4. **R99 fallback** catches high-risk subscribers with no product rule match
5. **High-risk subscribers never left on R00_MONITOR** — corrective override forces action

### Rule Catalog (14 Rules)

| ID | Rule | Priority | Coverage | Action |
|----|------|----------|----------|--------|
| R01 | **PREPAID_INFANT** — Prepaid + tenure ≤6 months | P1 | 1,413 (20.1%) | Welcome SMS + 20% bonus credit |
| R02 | **PREPAID_5G** — Prepaid on 5G network | P1 | 1,509 (21.4%) | 5G retention pack + migration assessment |
| R12 | **ECOSYSTEM_POWER_USER** — All 4 products active | P2 | Ecosystem | VIP loyalty preservation |
| R05 | **BILL_SHOCK** — Spend spike >25% | P2 | 582 (8.3%) | Bill shock SMS + plan review |
| R09 | **RUBIKA_INACTIVE** — Data-capable, no Rubika | P2 | Ecosystem | Rubika onboarding campaign |
| R10 | **EWANO_NON_ADOPTER** — No EWANO wallet | P2 | Ecosystem | EWANO activation + cashback |
| R11 | **HAMRAHMAN_LOW** — Low app engagement | P2 | Ecosystem | Hamrah Man onboarding |
| R03 | **VOLTE_ENABLE** — VoLTE capable, not adopted | P2 | — | VoLTE activation push |
| R04 | **VAS_ZERO** — Data-capable, no VAS | P2 | — | VAS starter bundle |
| R06 | **VAS_PARTIAL** — 1-2 VAS products | P3 | — | Cross-sell roaming + wallet |
| R08 | **POSTPAID_EARLY** — Postpaid first year | P3 | — | Loyalty discount + auto-pay |
| R07 | **LEGACY_2G** — Voice-only line | P3 | 1,101 (15.6%) | SIM swap + 4G migration |
| R00 | **MONITOR** — Low risk, no rule match | P4 | 552 (7.8%) | Quarterly health SMS |
| R99 | **FALLBACK** — High risk, no rule match | P1 | 0 (0.0%) | Retention desk callback |

### Key Findings

- **0% fallback rate** — every high-risk subscriber is covered by at least one product rule
- **42.1% P1 campaigns** — almost half of all actions require immediate attention
- **Top 5 rules cover 73%** of all subscribers
- **4 ecosystem rules** address product adoption gaps

### Campaign Cost Structure

| Tier | Cost | Description |
|------|------|-------------|
| C0 | None | Monitoring / health SMS only |
| C1 | Low | Automated SMS / app push, no agent |
| C2 | Medium | USSD / digital bundle / auto-credit |
| C3 | Medium-high | Optional outbound call queue |
| C4 | High | Retention desk call + ARPU-capped offer |

### Revenue Projection

| Scenario | Retained | Revenue (Toman) | ROI |
|----------|----------|-----------------|-----|
| Optimistic | 980 | 574,770,000 | 75,119% |
| Realistic | 428 | 138,672,000 | 15,112% |
| Conservative | 160 | 32,448,000 | 3,385% |

---

## Behavioral Segmentation Summary

### Methodology

Three clustering algorithms were compared across k=3–8 candidates:

| Method | Best k | Silhouette | Davies-Bouldin |
|--------|--------|-----------|----------------|
| **K-Means** | **3** | **0.330** | **1.185** |
| GMM | 3 | 0.250 | 1.689 |
| Agglomerative | 3 | 0.288 | 1.244 |

K-Means was selected based on highest silhouette score with clear margin (+0.042). The segmentation uses **9 behavioral dimensions**: tenure, lifetime ARPU, monthly spend, spend intensity, digital engagement, ecosystem services, VAS adoption, network generation, and age.

**Cluster stability (ARI = 0.999)** across 5 random seeds confirms robustness.

### The Three Segments

![Behavioral Segmentation](screenshots/behavioral.png)
*Figure 2: Behavioral Segmentation page showing the three K-Means clusters with their profiles, feature importance, and risk differentiation.*

#### 1. Premium Digital Engaged (37.3%, n=2,630)

- **Mean risk**: 0.256 (below average)
- **Profile**: High digital engagement, high VAS adoption, high ecosystem service count, high ARPU
- **Treatment**: Proactive premium retention with loyalty perks and early-access benefits
- **Primary channel**: Hybrid (digital + agent)

#### 2. Early-Life At-Risk Users (39.0%, n=2,745)

- **Mean risk**: 0.385 (1.4× average — highest)
- **Profile**: Short tenure, low digital engagement, newer network generation, moderate spend
- **Treatment**: Accelerate ecosystem onboarding: welcome campaigns, VAS trials, digital habit formation within first 90 days
- **Primary channel**: Digital + SMS

#### 3. Low-Engagement Stable (23.7%, n=1,668)

- **Mean risk**: 0.100 (0.37× average — lowest)
- **Profile**: Very low spend, low engagement, low ARPU, low VAS adoption
- **Treatment**: Standard stewardship with periodic monitoring; avoid unnecessary outreach
- **Primary channel**: Digital (app)

### Risk Differentiation

The segments show strong churn-risk separation:
- Highest-risk segment (Early-Life) has **3.8× the mean risk** of the lowest-risk segment (Low-Engagement Stable)
- This validates the behavioral features as meaningful risk discriminators

### Limitations (Explicit)

- **Descriptive, not causal** — Changing a subscriber's behavioral profile does not guarantee changed churn outcomes
- **Snapshot in time** — Periodic re-clustering is recommended as the subscriber base evolves
- **Moderate silhouette (0.33)** — Typical for telecom behavioral data; stability (ARI > 0.99) and clear risk differentiation compensate

---

## Product Surface Summary

Retnza delivers 9 operational dashboard pages, a bilingual interface, and structured BI exports:

### Dashboard Pages

#### 1. Executive Dashboard
![Executive Dashboard](screenshots/dashboard.png)
*Figure 3: Executive Dashboard showing top-level KPIs (total subscribers, churn rate, P1 actions), risk distribution bar chart, campaign priority breakdown, and ecosystem segment overview. This is the primary landing page for executive stakeholders.*

**Data sources**: `/api/v1/dashboard/kpis`, `/api/v1/dashboard/charts`, `/api/v1/model/health`, `/api/v1/ecosystem/summary`

#### 2. CRM Action Queue
![CRM Action Queue](screenshots/queue.png)
*Figure 4: CRM Action Queue with prioritized per-subscriber retention actions. Supports filtering by risk tier, priority, ecosystem segment, and queue type. Each row includes subscriber ID, risk score, rule ID, recommended action, campaign priority, and channel.*

**Data sources**: `/api/v1/recommendations`, `/api/v1/recommendations/action-queue/*`

#### 3. Subscriber Intelligence
![Subscriber Detail](screenshots/subscriber.png)
*Figure 5: Subscriber Detail page showing individual risk score, SHAP driver explanations (positive/negative), recommendation detail, ecosystem profile, campaign metadata, and governance versioning. This is the richest single-subscriber view.*

**Data sources**: `/api/v1/subscribers/{id}`, `/api/v1/shap/{id}`

#### 4. Campaign Playbook
![Campaign Playbook](screenshots/campaigns.png)
*Figure 6: Campaign Playbook showing retention campaign performance metrics, saturation analysis, and historical impact projections. Helps campaign managers plan and optimize retention efforts.*

**Data sources**: `/api/v1/reports/campaigns`, `/api/v1/reports/saturation`

#### 5. Ecosystem Analytics
![Ecosystem Analytics](screenshots/ecosystem.png)
*Figure 7: Ecosystem Analytics page with product adoption breakdowns (Rubika, EWANO, Hamrah Man, VoLTE), engagement levels, ecosystem segment distribution, and retention strategies by segment.*

**Data sources**: `/api/v1/ecosystem/summary`, `/api/v1/ecosystem/demographics`

#### 6. Model Health
![Model Health](screenshots/health.png)
*Figure 8: Model Health page showing drift detection (PSI metrics), stability metrics (CV mean/std for each family), score distribution histograms, and model health status indicators.*

**Data sources**: `/api/v1/model/drift`, `/api/v1/model/stability`

#### 7. Model Monitoring & Governance
![Model Monitoring & Governance](screenshots/model.png)
*Figure 9: Model Monitoring and Governance page displaying champion model metrics (PR-AUC, ROC-AUC, Brier, ECE), threshold policy comparison, artifact freshness, calibration transparency, and 10-safeguard trust panel.*

**Data sources**: `/api/v1/model/health`, `/api/v1/model/governance`

#### 8. Behavioral Segmentation
![Behavioral Segmentation](screenshots/behavioral.png)
*Figure 10: Behavioral Segmentation detail showing cluster profiles, PCA visualization, feature importance by cluster, and operational recommendations per segment.*

**Data sources**: `/api/v1/behavioral-segments/summary`

#### 9. Evidence & Insights
![Evidence & Insights](screenshots/evidence.png)
*Figure 11: Evidence & Insights page providing explainability artifacts, rule diagnostics, SHAP global importance, and behavioral segment cross-reference.*

**Data sources**: Multiple aggregated sources

### Bilingual Interface

The entire dashboard is available in English and Persian (Farsi):
- Persian digits (۰-۹) and RTL layout are fully supported
- Locale is persisted via `localStorage` and toggled via a language switcher
- Translation keys are managed via `frontend/src/i18n/` (en.json, fa.json)

### BI Export Layer

| Export | Format | Path | Use Case |
|--------|--------|------|----------|
| CRM Action Queue | CSV | `outputs/powerbi/crm_action_queue.csv` | Power BI, CRM import |
| Subscriber Recommendations | Parquet | `outputs/recommendations/subscriber_recommendations.parquet` | Advanced analytics |
| Export Manifest | JSON | `outputs/powerbi/powerbi_export_manifest.json` | Schema documentation |

---

## Governance / Trust Summary

### Governance Dashboard

The Governance Dashboard (accessible via `/model` page, governance tab) provides **10 safeguard checks**:

1. **Bundle schema compatibility** — Champion bundle version vs expected schema
2. **SHAP schema compatibility** — SHAP parquet version alignment
3. **Recommendation schema compatibility** — Recommendation parquet version alignment
4. **Feature contract validation** — Feature column names and types
5. **Artifact freshness** — Timestamps of all pipeline artifacts
6. **Calibration transparency** — Method, fit data, overfit risk, tradeoff note
7. **Threshold policy comparison** — Multiple operating policies with rationale
8. **Drift reference availability** — PSI-ready score and feature distributions
9. **Stability metrics** — CV mean/std across model families
10. **Production cautions** — Explicit tradeoff documentation

### Schema Versioning

Every pipeline stage produces versioned artifacts:

| Artifact | Schema Version |
|----------|---------------|
| Champion bundle | `champion-bundle-v4` |
| Modeling pipeline | `modeling-v4` |
| Feature engineering | `task4-v2` |
| SHAP explanations | `task7-shap-v4` |
| Recommendations | `task8-recommendations-v4` |
| Behavioral segments | `behavioral-segments-v2` |
| Analytics | `analytics-v1` |

### Wording Policy

All narratives use associative wording ("associated with", "observed relationship"). No causal claims are made. SHAP narratives inform but never override rule-based actions.

> **Key principle**: "Ecosystem metrics are associative — not causal product effects."

---

## Limitations

### Data Limitations

- **No temporal dimension** — Dataset is a single snapshot without observation dates. Temporal drift assessment uses tenure as a weak proxy only
- **No geographic data** — Location-based segmentation is not supported
- **Single market** — Model trained on a single operator dataset; transferability is unvalidated
- **Moderate size** — 7,043 subscribers is sufficient for ML but limits deep subgroup analysis

### Modeling Limitations

- **PR-AUC trade-off** — Calibration improves Brier/ECE but reduces PR-AUC by 3.6% (from 0.657 to 0.633)
- **SHAP is narrative-only** — SHAP explains the base model, not calibrated scores; SHAP never selects actions
- **No uplift modeling** — The platform does not estimate treatment effects; "recommended action" is a rule-based suggestion, not a predicted outcome
- **Temporal proxy limitation** — Tenure-based stability splits are explicitly documented as a "weak proxy"

### Product Limitations

- **Database bootstrap**: Uses `create_all` for schema creation (not full Alembic migration chain)
- **Redis cache**: Configured but not implemented for dashboard endpoints
- **WebSocket push**: Action queue requires manual page refresh for updates
- **Backend CI**: Tests exist but are not wired into automated CI
- **Snapshot tests**: No UI snapshot tests
- **i18n coverage**: No automated check for translation key completeness
- **Performance**: No load tests for dashboard or queue endpoints

### Model Performance Caveat

The holdout test set performance (PR-AUC 0.657) is measured on a stratified split, which may overestimate real-world performance compared to a time-based split. The tenure-based proxy analysis provides a more conservative estimate (PR-AUC 0.357). True temporal validation would require timestamped data.

---

## Final Verdict

### Strengths

1. **End-to-end ML pipeline** — From raw CSV to operational dashboard, every stage is implemented, versioned, and tested
2. **Clear ML-to-business separation** — Model scores are one input; retention actions are determined by business rules, not ML
3. **Strong risk differentiation** — Top decile lift of 2.8× and 86.8% recall at operating threshold
4. **Comprehensive explainability** — SHAP global and per-subscriber with explicit causal caveats
5. **Production engineering quality** — FastAPI backend, Next.js 15 frontend, bilingual EN/FA, Docker Compose, structured BI exports, 169 frontend tests
6. **Behavioral segmentation** — 3 robust clusters with ARI > 0.99 stability and 3.8× risk ratio between highest/lowest
7. **Governance-ready** — Schema versioning, compatibility checks, explicit tradeoff documentation, 10-safeguard trust panel
8. **Bilingual by design** — Full English and Persian support with Persian digits and RTL layout

### Weaknesses

1. **No temporal validation** — The single-snapshot dataset prevents true time-series evaluation
2. **No causal inference** — Recommendations are rule-based, not optimized for treatment effects
3. **Moderate dataset size** — 7K subscribers limits model complexity and subgroup analysis
4. **Missing production features** — Redis caching, WebSocket push, CI integration, load testing

### Engineering Maturity Assessment

**Stage 4: Cohesive Architecture** — The platform demonstrates clean separation of concerns across 7 pipeline stages, schema-versioned artifacts, comprehensive test coverage, bilingual UI, and documented engineering tradeoffs. It is not yet at Stage 5 (Observable & Self-Healing) due to missing monitoring infrastructure, automated CI, and production-grade schema migrations.

### Judging Summary

Retnza delivers a fully operational platform:
- An interactive bilingual dashboard with 9 operational pages
- A trained and calibrated churn model with documented performance
- 14 deterministic retention rules with 0% fallback rate
- Behavioral segmentation with 3 interpretable clusters
- Full SHAP explainability with associative caveats
- Governance infrastructure with versioned artifacts and compatibility checks
- Structured BI exports for downstream CRM and analytics tools

The project stands out for its **engineering completeness** (ML pipeline → API → bilingual dashboard → BI export → governance), its **clear separation of ML scoring from business rules**, and its **professional bilingual (English/Persian) presentation** suitable for an Iranian telecom operator like MCI.

---

## Repository File Map

| Path | Purpose |
|------|---------|
| `preprocessing/` (7 modules) | Raw CSV → cleaned data |
| `feature_engineering/` (7 modules) | 47 engineered features |
| `modeling/` (16 modules) | Training, selection, calibration, SHAP, drift, governance |
| `recommendation/` (8 modules) | 14 deterministic retention rules |
| `analytics/` (10 modules) | Executive summaries, segmentation, simulations |
| `backend/app/` | FastAPI REST API (20 endpoints) |
| `frontend/src/` | Next.js 15 dashboard (9 pages, bilingual) |
| `outputs/` | All ML artifacts, BI exports |
| `docs/` (12 files) | Comprehensive documentation |
| `scripts/` (11 scripts) | Pipeline orchestration |
| `docker/` | Docker Compose + Dockerfiles |

---

## Screenshot Inventory

| File | Page | Content |
|------|------|---------|
| `screenshots/dashboard.png` | Executive Dashboard | KPIs, risk distribution, queue summary |
| `screenshots/queue.png` | CRM Action Queue | Filterable retention action table |
| `screenshots/subscriber.png` | Subscriber Detail | SHAP drivers, scores, recommendation |
| `screenshots/campaigns.png` | Campaign Playbook | Campaign performance, saturation |
| `screenshots/ecosystem.png` | Ecosystem Analytics | Product adoption, segments |
| `screenshots/health.png` | Model Health | Drift, stability, score distribution |
| `screenshots/model.png` | Model Monitoring | Metrics, governance, thresholds |
| `screenshots/behavioral.png` | Behavioral Segmentation | Cluster profiles, risk differentiation |
| `screenshots/evidence.png` | Evidence & Insights | SHAP importance, rule diagnostics |

---

*Report generated: May 29, 2026*
*Platform version: 1.0.0*

