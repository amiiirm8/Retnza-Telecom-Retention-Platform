# Retnza — Telecom Retention Intelligence Platform

**Reduce churn. Explain why. Recommend action.**

Retnza is an enterprise-grade telecom churn prediction and retention decision-support platform. It identifies subscribers at risk of churn, explains *why* they are at risk using SHAP driver analysis, recommends specific retention actions via 14 deterministic business rules, and delivers insights through an interactive bilingual (English / Persian) dashboard with 9 operational views.

---

## Quick Overview

| Layer | Technology | Status |
|-------|-----------|--------|
| ML Pipeline | Python (scikit-learn, SHAP, imbalanced-learn) | **Complete** — 47 features, Random Forest champion, Isotonic calibration |
| Recommendation Engine | Python — 14 deterministic rules | **Complete** — 0% fallback rate, 4 ecosystem rules |
| Backend API | FastAPI + SQLAlchemy + PostgreSQL | **Complete** — 20 REST endpoints, JWT auth, rate limiting |
| Frontend Dashboard | Next.js 15 + TypeScript + Recharts | **Complete** — 9 pages, bilingual EN/FA, 169 tests |
| BI Export | CSV + Parquet | **Complete** — CRM-ready action queue, Power BI manifest |
| Deployment | Docker Compose | **Complete** — PostgreSQL 16, Redis 7, FastAPI, Next.js |

---

## Contents

- [What Problem It Solves](#what-problem-it-solves)
- [Architecture](#architecture)
- [How to Run](#how-to-run)
- [Dashboard Pages](#dashboard-pages)
- [Key Outcomes](#key-outcomes)
- [Behavioral Segmentation](#behavioral-segmentation)
- [Recommendation System](#recommendation-system)
- [Governance & Trust](#governance--trust)
- [Files & Artifacts](#files--artifacts)
- [How to Reproduce Results](#how-to-reproduce-results)
- [Limitations](#limitations)

---

## What Problem It Solves

Telecom operators lose 20–30% of subscribers annually. Retention teams need to know **who** is at risk, **why**, and **what to do** — quickly and at scale.

Retnza answers four questions:

| Question | How Retnza Answers It |
|----------|-----------------------|
| **Who** is at risk? | Churn risk engine scores every subscriber with a calibrated probability. |
| **Why** are they at risk? | Per-subscriber SHAP driver analysis identifies specific risk signals. |
| **What** should we do? | Deterministic rule engine (14 rules) maps risk + profile to a retention play. |
| **How** do we act? | CRM Action Queue, campaigns, ecosystem analytics, BI export. |

---

## Architecture

```
Raw CSV → Cleaning → Feature Engineering (47) → Champion Model (RF) → Calibration (Isotonic)
                                                                 ↓
                       SHAP Explainability ← Risk Scoring + Tiering
                                                                 ↓
                                              Rule Engine (R01–R13)
                                                                 ↓
                                    Behavioral Segmentation (K-Means / 3)
                                                                 ↓
                                         ┌──────────────────────────┐
                                         │  FastAPI (REST + JWT)     │
                                         │  PostgreSQL (artifacts)   │
                                         └──────────────────────────┘
                                                                 ↓
                              ┌───────────────────────────┐
                              │  Next.js Dashboard (EN/FA) │
                              │  CRM Action Queue          │
                              │  Behavioral Segments       │
                              │  Campaign / Ecosystem      │
                              │  Governance / Health       │
                              └───────────────────────────┘
                                                                 ↓
                                               CSV / Parquet Export
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Dual scores**: raw + calibrated | Raw for ranking (version-stable), calibrated for CRM decisions |
| **Risk tiers** at 0.65 / 0.30 / 0.15 | Very High, High, Medium, Low (executive labels in UI) |
| **Deterministic rules only** | ML never selects actions; rules are pure functions of features |
| **SHAP is narrative-only** | Explains but never overrides rule-based recommendations |
| **Bilingual EN/FA** | Full Persian support with digits and RTL layout |

---

## How to Run

### Prerequisites

- Python 3.11+, Node.js 20+, Docker
- 4 GB free disk space for ML artifacts

**Important:** The champion model was trained with **numpy 2.x** and requires `numpy>=2.0`
and `scipy>=1.14` (for binary compatibility). See `requirements.txt` for exact constraints.

### 1. Run the full pipeline

```bash
# Set up Python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Pipeline steps
.venv/bin/python scripts/build_datasets.py      # Clean raw data
.venv/bin/python scripts/build_features.py      # Engineer 47 features
.venv/bin/python scripts/train_champion.py      # Train + calibrate + select
.venv/bin/python scripts/generate_recommendations.py  # Apply rules
.venv/bin/python scripts/export_powerbi_dataset.py    # Export CRM queue
```

### 2. Start the platform

```bash
# Start PostgreSQL and Redis via Docker
docker compose -f docker/docker-compose.yml up postgres redis -d

# Install backend deps & seed DB
pip install -r backend/requirements.txt
python backend/scripts/seed_db.py

# Start API
cd backend && uvicorn app.main:app --reload --port 8000

# Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

**Or use the convenience script:**
```bash
scripts/start_platform.sh
```

### 3. Access the dashboard

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Dashboard |
| http://localhost:8000/docs | API docs |
| Login: `admin@retnza.local` / `admin123` | |

### Testing

```bash
# Frontend (169 tests)
cd frontend && npm test

# Backend (5 test suites, 39 tests)
cd backend && python -m pytest -v
```

---

## Dashboard Pages

### 1. Executive Dashboard
![Dashboard](screenshots/dashboard.png)
*Top-level KPIs: subscriber count, churn rate, P1 actions, risk distribution, campaign priorities, ecosystem segments.*

### 2. CRM Action Queue
![CRM Queue](screenshots/queue.png)
*Prioritized per-subscriber retention actions with filters by risk tier, priority, ecosystem segment, queue type.*

### 3. Subscriber Intelligence
![Subscriber](screenshots/subscriber.png)
*Per-subscriber risk score + SHAP drivers + recommendation + ecosystem profile + campaign metadata.*

### 4. Campaign Playbook
![Campaigns](screenshots/campaigns.png)
*Campaign performance metrics, saturation analysis, historical impact projections.*

### 5. Ecosystem Analytics
![Ecosystem](screenshots/ecosystem.png)
*Product adoption (Rubika, EWANO, Hamrah Man, VoLTE), engagement levels, retention strategies by segment.*

### 6. Model Health
![Health](screenshots/health.png)
*Drift detection (PSI), stability metrics, score distribution, governance summary.*

### 7. Model Monitoring & Governance
![Model](screenshots/model.png)
*Champion metrics, threshold policy comparison, artifact freshness, 10-safeguard trust panel.*

### 8. Behavioral Segmentation
![Behavioral](screenshots/behavioral.png)
*3 K-Means clusters with profiles, feature importance, risk differentiation.*

### 9. Evidence & Insights
![Evidence](screenshots/evidence.png)
*SHAP global importance, rule diagnostics, explainability artifacts.*

---

## Key Outcomes

### Model Performance (Holdout Test)

| Metric | Value |
|--------|-------|
| PR-AUC (uncalibrated) | 0.657 |
| PR-AUC (calibrated) | 0.633 |
| ROC-AUC | 0.844 |
| Brier (uncalibrated) | 0.159 |
| Brier (calibrated) | **0.136** |
| ECE (calibrated) | **0.025** |
| Operating recall | **86.8%** |
| Top-decile lift | **2.80×** |

### Risk Distribution (7,043 subscribers)

| Tier | Threshold | Count | % |
|------|-----------|-------|---|
| Very High | ≥0.65 | 664 | 9.4% |
| High | ≥0.30 | 1,826 | 25.9% |
| Medium | ≥0.15 | 1,664 | 23.6% |
| Low | <0.15 | 2,889 | 41.0% |

### Revenue Impact Projection

| Scenario | Retained | Revenue (Toman) | ROI |
|----------|----------|----------------|-----|
| Optimistic | 980 | 574,770,000 | 75,119% |
| Realistic | 428 | 138,672,000 | 15,112% |
| Conservative | 160 | 32,448,000 | 3,385% |

### Top Rules by Coverage

| Rule | Count | % |
|------|-------|---|
| R02_PREPAID_5G | 1,509 | 21.4% |
| R01_PREPAID_INFANT | 1,413 | 20.1% |
| R07_LEGACY_2G | 1,101 | 15.6% |
| R05_BILL_SHOCK | 582 | 8.3% |
| R00_MONITOR | 552 | 7.8% |

---

## Behavioral Segmentation

### Method

K-Means clustering on 9 behavioral dimensions (tenure, ARPU, spend, engagement, ecosystem services, VAS, network generation, age). k=3 selected by silhouette score (0.330) with ARI stability of 0.999.

### The Three Segments

| Segment | Size | Mean Risk | Risk vs Avg | Treatment |
|---------|------|-----------|-------------|-----------|
| Early-Life At-Risk Users | 2,745 (39.0%) | 0.385 | **1.43×** (highest) | Accelerate ecosystem onboarding |
| Premium Digital Engaged | 2,630 (37.3%) | 0.256 | 0.95× | Loyalty perks, proactive retention |
| Low-Engagement Stable | 1,668 (23.7%) | 0.100 | **0.37×** (lowest) | Standard stewardship, monitoring |

**Risk ratio (highest/lowest): 3.8×**

---

## Recommendation System

### Architecture

14 deterministic rules evaluated in precedence order:

1. **P1 rules** (infant prepaid, prepaid 5G) — highest urgency
2. **P2 rules** — ecosystem onboarding, bill shock, VoLTE, VAS zero
3. **P3 rules** — VAS cross-sell, postpaid early, legacy migration
4. **P4** — monitoring only

### Key Features

- **0% fallback rate** — all high-risk subscribers covered by product rules
- **Ecosystem rules** (R09-R12) target product adoption gaps
- **Safety net**: high-risk subscribers never left on R00_MONITOR
- **Cost tiers**: C0 (monitoring) to C4 (retention desk call)

### BI Export

| Export | Format | Path |
|--------|--------|------|
| CRM Action Queue | CSV | `outputs/powerbi/crm_action_queue.csv` |
| Recommendations | Parquet | `outputs/recommendations/subscriber_recommendations.parquet` |
| Manifest | JSON | `outputs/powerbi/powerbi_export_manifest.json` |

---

## Governance & Trust

### Safeguards

1. Schema compatibility (bundle, SHAP, recommendations)
2. Feature contract validation
3. Artifact freshness tracking
4. Calibration transparency (method, fit data, overfit risk)
5. Threshold policy comparison with rationale
6. Drift reference availability
7. Cross-validation stability metrics
8. Production tradeoff documentation

### Wording Policy

All narratives use associative wording. No causal claims. SHAP informs but never overrides rules.

---

## Files & Artifacts

### Critical Files

| File | Purpose |
|------|---------|
| `preprocessing/pipeline.py` | Data cleaning pipeline |
| `feature_engineering/builders.py` | 47 feature construction |
| `modeling/champion.py` | Champion selection logic |
| `modeling/explainability.py` | SHAP computation |
| `modeling/calibration.py` | Isotonic calibration |
| `recommendation/engine.py` | Rule orchestration |
| `recommendation/rules.py` | 14 rule definitions |
| `analytics/behavioral_segmentation.py` | K-Means clustering |
| `backend/app/main.py` | FastAPI entry point |
| `frontend/src/app/(app)/` | 9 Next.js pages |

### Key Outputs

| Path | Content |
|------|---------|
| `outputs/champion/champion_manifest.json` | Full model performance, thresholds |
| `outputs/champion/champion_model.joblib` | Trained Random Forest model |
| `outputs/explainability/global_shap_importance.csv` | Global SHAP rankings |
| `outputs/explainability/subscriber_shap_values.parquet` | Per-subscriber SHAP |
| `outputs/analytics/behavioral_segments_summary.json` | Cluster profiles |
| `outputs/analytics/executive_summary.json` | KPI narratives |
| `outputs/recommendations/recommendation_manifest.json` | Rule coverage stats |
| `outputs/powerbi/crm_action_queue.csv` | CRM-ready export |

---

## How to Reproduce Results

```bash
# 1. Clean data
python scripts/build_datasets.py

# 2. Build features
python scripts/build_features.py

# 3. Train champion model
python scripts/train_champion.py

# 4. Generate recommendations
python scripts/generate_recommendations.py

# 5. Export for BI
python scripts/export_powerbi_dataset.py

# 6. Run analytics
python analytics/run_all.py

# 7. Seed database & start API
python backend/scripts/seed_db.py
uvicorn app.main:app --app-dir backend

# 8. Start frontend
cd frontend && npm run dev
```

---

## Limitations

- **No temporal validation** — single snapshot dataset prevents true time-series evaluation
- **No causal inference** — recommendations are rule-based, not optimized for treatment effects
- **Moderate dataset size** — 7K subscribers limits deep subgroup analysis
- **Missing production features** — Redis caching, WebSocket push, automated CI, load testing
- **SHAP is narrative-only** — explains base model, not calibrated scores
- **Database bootstrap**: Uses `create_all` (not full Alembic migrations)
- **Snapshot tests**: No UI snapshot tests

---

## Dataset

- **7,043 subscribers**, ~26.5% historical churn rate
- **47 engineered features** from billing, usage, and product data
- Source: `MCI_Challenge_FinalDataset.csv` (not redistributed)
- All financial values in Iranian Toman

---

## License

MIT License. See [LICENSE](LICENSE) for details.

> **Note:** The raw dataset (`MCI_Challenge_FinalDataset.csv`) is not redistributed.
> Users must obtain the original dataset separately to reproduce the pipeline end-to-end.

---

## Engineering Maturity

**Stage 4: Cohesive Architecture** — Clean separation of concerns across 7 pipeline stages, schema-versioned artifacts, comprehensive test coverage, bilingual UI, documented engineering tradeoffs.
