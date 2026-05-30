# Retnza — Telecom Retention Intelligence Platform

**Reduce churn. Explain why. Recommend action.**

📚 **Documentation available in:**

| Language | Final Report | Executive Summary | README |
|----------|-------------|-------------------|--------|
| 🇬🇧 English | [`FINAL_REPORT_EN.md`](FINAL_REPORT_EN.md) | [`EXECUTIVE_SUMMARY_EN.md`](EXECUTIVE_SUMMARY_EN.md) | [`README_EN.md`](README_EN.md) |
| 🇮🇷 Persian (فارسی) | [`FINAL_REPORT_FA.md`](FINAL_REPORT_FA.md) | [`EXECUTIVE_SUMMARY_FA.md`](EXECUTIVE_SUMMARY_FA.md) | [`README_FA.md`](README_FA.md) |

Retnza is an enterprise-grade telecom churn prediction and retention
decision-support platform. It identifies subscribers at risk of churn,
explains *why* they are at risk using SHAP driver analysis, recommends
specific retention actions via deterministic business rules, and delivers
insights through an interactive bilingual (English / Persian) dashboard.

## The Problem

Telecom operators lose 20–30% of subscribers annually. Retention teams need
to know **who** is at risk, **why**, and **what to do about it** — quickly
and at scale. Traditional approaches rely on siloed tools: raw model scores
without explanation, manual rule writing, separate BI exports, and no
operational dashboards.

## The Solution

Retnza delivers a single integrated platform that answers four questions:

| Question | How Retnza Answers It |
|----------|-----------------------|
| **Who** is at risk? | Churn risk engine scores every subscriber with a calibrated probability. Raw RF score for ranking, isotonic-calibrated for business decisions. |
| **Why** are they at risk? | Per-subscriber SHAP driver analysis identifies the specific signals pushing churn risk up or down. |
| **What** should we do? | Deterministic rule engine (14 rules) maps risk + profile to a specific retention play with channel, offer, and urgency. |
| **How** do we act? | CRM Action Queue, campaign playbook, ecosystem analytics, and structured BI export provide operational surfaces. |

## Architecture Overview

```
Raw CSV → Cleaning → Feature Engineering → Champion Model → Calibration
                                                          ↓
                        SHAP Explainability ← Risk Scoring + Tiering
                                                          ↓
                                                  Rule Engine (R00–R13)
                                                          ↓
                                          Behavioral Segmentation
                                          (K-Means / 3 segments)
                                                          ↓
                                           ┌──────────────────────────┐
                                           │  FastAPI (REST + JWT)     │
                                           │  PostgreSQL (artifacts)   │
                                           │  Redis (future cache)     │
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
                                                (Power BI, CRM)
```

### Key Design Decisions

| Topic | Decision |
|-------|----------|
| Risk ranking | Raw Random Forest score (`churn_probability_raw`) preserves relative ordering across model versions |
| Business probability | Isotonic-calibrated score (`churn_probability`) drives risk tiers, actions, and reporting |
| Risk tiers | Very High ≥ 0.65, High ≥ 0.30, Medium ≥ 0.15, Low < 0.15 (UI displays as Critical, At Risk, Watchlist, Stable) |
| Retention actions | Deterministic rules only (R01–R13, R00 monitor, R99 fallback) — ML never selects actions |
| Explainability | SHAP on base model for narrative overlay only — not causal, not action-driving |
| Business intelligence | Interactive web dashboard (primary) + CSV/Parquet export for Power BI / CRM (secondary) |
| Bilingual support | Full English and Persian (Farsi) with Persian digits, RTL-aware formatting |
| ML→UI translation | Backend returns ML-native tiers; frontend maps to executive labels via a single canonical resolver |

## What's Included

| Layer | Technology | Contents |
|-------|-----------|----------|
| **ML Pipeline** | Python (scikit-learn, SHAP, imbalanced-learn) | Preprocessing, feature engineering (47 features), model training/evaluation/selection, calibration, SHAP explainability, drift detection, governance checks |
| **Recommendation Engine** | Python | 14 deterministic business rules (R00–R13 + R99 fallback), channel resolution, ecosystem analytics, campaign costing |
| **Backend API** | FastAPI + SQLAlchemy + PostgreSQL | 20 REST endpoints, JWT auth, rate limiting, artifact validation, real-time scoring |
| **Frontend Dashboard** | Next.js 15 + TypeScript + Recharts | 9 dashboard pages, bilingual EN/FA, CRM Action Queue, ecosystem analytics, governance oversight, model health monitoring |
| **BI Export** | CSV + Parquet | CRM-ready action queue, Power BI-compatible dataset, structured manifest |
| **Deployment** | Docker Compose | PostgreSQL 16, Redis 7, FastAPI, Next.js |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for PostgreSQL and Redis)
- 4 GB free disk space for ML artifacts

### 1. Run the full pipeline

```bash
# Set up Python environment
python3 -m venv .venv
source .venv/bin/activate   # or: .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Place MCI_Challenge_FinalDataset.csv in data/raw/, then:
.venv/bin/python scripts/build_datasets.py      # Clean raw data
.venv/bin/python scripts/build_features.py      # Engineer 47 features
.venv/bin/python scripts/train_champion.py      # Train + calibrate + select champion
.venv/bin/python scripts/generate_recommendations.py  # Apply rules
.venv/bin/python scripts/export_powerbi_dataset.py    # Export CRM queue
```

### 2. Start the platform

```bash
# Start PostgreSQL and Redis via Docker
docker compose -f docker/docker-compose.yml up postgres redis -d

# Install backend dependencies
pip install -r backend/requirements.txt

# Seed the database
python backend/scripts/seed_db.py

# Start the API
cd backend && uvicorn app.main:app --reload --port 8000

# In another terminal, start the frontend
cd frontend && npm install && npm run dev
```

Or use the convenience script for macOS:

```bash
scripts/start_platform.sh
```

### 3. Access the dashboard

- **Dashboard**: http://localhost:3000
- **API docs**: http://localhost:8000/docs
- **Login**: `admin@retnza.local` / `admin123`

## Testing

### Frontend (8 suites, 169 tests)

```bash
cd frontend
npm test                           # Run all tests
npm run test:ci                    # CI mode with coverage
npx jest --watch                   # Watch mode
```

Tests cover: risk tier mapping, governance labels, label resolution, recommendation catalog, narrative rendering, formatting (EN/FA), safety edge cases, badge rendering.

### Backend (5 test suites, 39 tests)

```bash
cd backend
pip install -r requirements.txt
python -m pytest -v                # Run all backend tests
python -m pytest app/tests/test_schema_contracts.py -v  # Specific suite
```

Tests cover: API endpoints, ML pipeline integrity, recommendation rule determinism, schema contract integrity, integration checks. No database required.

## Dashboard Pages

| Page | Purpose |
|------|---------|
| **Executive Dashboard** | Top-level KPIs, risk distribution, campaign priorities, churn by SIM type, ecosystem segments, CRM queue distribution |
| **CRM Action Queue** | Prioritized per-subscriber retention actions with filter by queue, priority, risk tier, ecosystem segment |
| **Subscriber Intelligence** | Search subscribers, view per-subscriber risk + SHAP drivers + recommendation detail |
| **Ecosystem Analytics** | Ecosystem product adoption, engagement levels, retention strategies by segment |
| **Behavioral Segmentation** | K-Means clustering (3 segments), distinguishing features, operational priorities |
| **Evidence & Insights** | Interactive Q&A with confidence assessment, EDA insights, evidence layers, retention actions |
| **Campaign Playbook** | Campaign performance, saturation analysis, historical impact |
| **Model Health** | Drift detection (PSI), stability metrics, score distribution, governance summary |
| **Governance Dashboard** | 10-safeguard trust panel, threshold policy comparison, artifact freshness, calibration transparency |

## BI / Export Layer

The dashboard is the primary BI surface. For downstream integration:

| Export | Format | Path | Use Case |
|--------|--------|------|----------|
| CRM Action Queue | CSV | `outputs/powerbi/crm_action_queue.csv` | Power BI, CRM import, spreadsheet analysis |
| Subscriber Recommendations | Parquet | `outputs/recommendations/subscriber_recommendations.parquet` | Advanced analytics, Python/R workflows |
| Export Manifest | JSON | `outputs/powerbi/powerbi_export_manifest.json` | Schema documentation, automation |

The Action Queue includes: subscriber ID, risk score (raw + calibrated), risk tier, rule ID, recommended action, campaign priority (P1–P4), primary/secondary channel, cost tier, urgency, CRM queue assignment, and ecosystem segment.

## Repository Organization

```
├── preprocessing/     # Raw CSV → cleaned data (column mapping, QC, validation)
├── feature_engineering/  # Cleaned data → 47 engineered features (5 conceptual layers)
├── modeling/          # ML training, evaluation, calibration, champion selection, SHAP
├── recommendation/    # Deterministic retention rules engine (14 rules)
├── analytics/         # Post-pipeline analysis (executive summaries, simulations)
├── backend/           # FastAPI application (REST API, ORM, schemas, migrations)
│   ├── app/
│   │   ├── api/v1/endpoints/  # 9 endpoint modules
│   │   ├── models/            # 8 SQLAlchemy ORM models
│   │   ├── schemas/           # Pydantic API contracts
│   │   ├── services/          # ML, dashboard, report services
│   │   ├── core/              # Config, security, DI, artifact validation
│   │   └── tests/             # 5 test suites
│   ├── alembic/               # DB migration revisions
│   └── scripts/               # seed_db.py
├── frontend/          # Next.js 15 TypeScript application
│   ├── src/app/       # 7 route pages + login
│   ├── src/components/  # 34 reusable UI components
│   ├── src/lib/       # Canonical translation layer (risk labels, format, governance)
│   └── src/__tests__/  # 8 test suites
├── scripts/           # Pipeline orchestration scripts
├── outputs/           # All ML artifacts + BI exports
├── data/              # Raw, cleaned, feature, inference, schema data
├── docker/            # Docker Compose + Dockerfiles
└── docs/              # 12 documentation files
```

## Documentation

| Topic | Document |
|-------|----------|
| Platform architecture | [PLATFORM_ARCHITECTURE.md](docs/PLATFORM_ARCHITECTURE.md) |
| Data understanding | [DATA_UNDERSTANDING.md](docs/DATA_UNDERSTANDING.md) |
| Data preprocessing | [DATA_PREPROCESSING.md](docs/DATA_PREPROCESSING.md) |
| Exploratory analysis | [EXPLORATORY_ANALYSIS.md](docs/EXPLORATORY_ANALYSIS.md) |
| Signal engineering | [SIGNAL_ENGINEERING.md](docs/SIGNAL_ENGINEERING.md) |
| Baseline models | [BASELINE_MODELING.md](docs/BASELINE_MODELING.md) |
| Champion model | [CHAMPION_MODEL.md](docs/CHAMPION_MODEL.md) |
| Explainability + recommendations | [EXPLAINABILITY_RECOMMENDATIONS.md](docs/EXPLAINABILITY_RECOMMENDATIONS.md) |
| Recommendation engine | [RECOMMENDATION_ENGINE.md](docs/RECOMMENDATION_ENGINE.md) |
| Business intelligence | [BUSINESS_INTELLIGENCE.md](docs/BUSINESS_INTELLIGENCE.md) |
| Database bootstrap | [MIGRATION_AND_BOOTSTRAP.md](docs/MIGRATION_AND_BOOTSTRAP.md) |

## Known Limitations

- **Database bootstrap**: Uses `create_all` for schema creation (not full Alembic migration chain) — safe and idempotent, but not production-grade for schema evolution.
- **Redis cache**: Configured but not yet implemented for dashboard endpoints.
- **WebSocket push**: Action queue requires manual page refresh for updates.
- **Backend CI**: Tests exist but are not wired into automated CI (manual `pytest` execution required).
- **Snapshot tests**: No UI snapshot tests — rendering changes are verified manually.
- **i18n coverage**: No automated check for translation key completeness.
- **Performance**: No load tests for dashboard or queue endpoints.

## Dataset

- **7,043 subscribers**, ~26.5% historical churn rate
- **47 engineered features** from raw telecom billing, usage, and product data
- No geographic data in source
- Source: `MCI_Challenge_FinalDataset.csv` (not redistributed)

## Reproduction

Full step-by-step reproduction instructions available in
[`REPRODUCTION_GUIDE.md`](REPRODUCTION_GUIDE.md).

## License

MIT License. See [LICENSE](LICENSE) for details.

> **Note:** The raw dataset (`MCI_Challenge_FinalDataset.csv`) is not redistributed.
> Users must obtain the original dataset separately to reproduce the pipeline end-to-end.
