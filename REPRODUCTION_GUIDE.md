# Retnza — Reproduction Guide

This guide covers how to reproduce the Retnza telecom retention intelligence platform from source.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | 3.11.9 tested |
| Node.js | 20+ | 20.x or later |
| PostgreSQL | 16+ | Required for backend API |
| Redis | 7+ | Optional (rate limiting) |
| Docker | 24+ | Optional (containerized setup) |
| Disk space | 4 GB | ML artifacts + dependencies |

---

## Quick Start (Docker)

```bash
# 1. Start infrastructure
docker compose -f docker/docker-compose.yml up -d

# 2. Backend API runs at http://localhost:8000
# 3. Frontend dashboard runs at http://localhost:3000
# 4. Login: admin@retnza.local / admin123
```

---

## Manual Setup

### 1. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Database

```bash
# Ensure PostgreSQL is running, then:
cd backend
python -m scripts.seed_db
```

### 3. Backend API

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### 4. Frontend Dashboard

```bash
cd frontend
npm install
npm run dev
```

---

## Full Pipeline Reproduction

### Step 1: Raw data

Place `MCI_Challenge_FinalDataset.csv` in `data/raw/`. The dataset contains 7,043 subscriber records with churn labels.

### Step 2: Preprocessing

```bash
python scripts/build_datasets.py
```

Outputs: `data/cleaned/subscribers_cleaned.parquet`

### Step 3: Feature engineering

```bash
python scripts/build_features.py
```

Outputs: `data/features/subscribers_featured.parquet`, `data/features/feature_manifest.json`

### Step 4: Model training

```bash
python scripts/train_champion.py
```

Outputs:
- `outputs/champion/champion_model.joblib` (Random Forest + calibrator bundle)
- `outputs/champion/champion_manifest.json`
- `outputs/baselines/baseline_results.json`

### Step 5: Explanations

```bash
python scripts/run_shap_analysis.py
```

Outputs: `outputs/explainability/` (SHAP values, importance, plots)

### Step 6: Recommendations

```bash
python scripts/generate_recommendations.py
```

Outputs:
- `outputs/recommendations/subscriber_recommendations.parquet`
- `outputs/analytics/rule_precision_summary.json`

### Step 7: Analytics & reporting

```bash
python analytics/run_all.py
```

Outputs:
- `outputs/analytics/executive_summary.json`
- `outputs/analytics/behavioral_segments_summary.json`
- `outputs/analytics/ecosystem_demographic_analytics.json`

### Step 8: Seed database & start API

```bash
cd backend
python -m scripts.seed_db
python -m uvicorn app.main:app --reload --port 8000
```

### Step 9: Launch dashboard

```bash
cd frontend
npm run dev
```

---

## Running Tests

### Frontend

```bash
cd frontend
npm test                         # All 169 tests
npm run test:ci                  # CI mode with coverage
npx jest --watch                 # Watch mode
```

### Backend

```bash
cd backend
python -m pytest -v              # All 39 tests
python -m pytest app/tests/test_schema_contracts.py -v  # Specific suite
```

### Test coverage

| Suite | File | Tests | DB Required |
|-------|------|-------|-------------|
| API endpoints | `app/tests/test_endpoints.py` | Health, login, predict (mocked) | No |
| ML pipeline | `app/tests/test_ml.py` | Feature columns, risk tiers, scoring | No |
| Recommendation rules | `app/tests/test_recommendation_rules.py` | Tier boundaries, precedence, config | No |
| Schema contracts | `app/tests/test_schema_contracts.py` | KPI/chart/recommendation field integrity | No |
| Integration | `app/tests/test_integration_checks.py` | Artifact bootstrap, FastAPI wiring | No |

---

## Expected Outputs

After full pipeline execution:

| Path | Contents |
|------|----------|
| `outputs/champion/` | Champion model bundle (Random Forest + isotonic calibrator) |
| `outputs/eda/` | Churn rate CSVs by SIM type, generation, tenure, VoLTE |
| `outputs/explainability/` | Global/local SHAP importance, beeswarm/dependence plots |
| `outputs/recommendations/` | Per-subscriber recommendation assignments |
| `outputs/analytics/` | Executive summaries, segment profiles, retention simulation |
| `outputs/powerbi/` | CRM-ready action queue CSV + manifest |
| `outputs/governance/` | Schema compatibility, calibration health, drift snapshots |

---

## Login Credentials

- **Email:** `admin@retnza.local`
- **Password:** `admin123`

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: numpy` | Missing dependencies | `pip install -r requirements.txt` |
| Backend won't start (DB error) | PostgreSQL not running | `docker compose up -d` or start local PostgreSQL |
| Frontend build fails | Missing node_modules | `cd frontend && npm install` |
| Model file not found | Pipeline not run | Run `python scripts/train_champion.py` |
| SHAP values not loading | SHAP not generated | Run `python scripts/run_shap_analysis.py` |
| Empty dashboard charts | Artifacts not seeded | `cd backend && python -m scripts.seed_db` |
| Rate limit errors | Too many requests | Wait or adjust `RATE_LIMIT` in `.env` |

---

## Architecture Diagram

```
Raw CSV (7K subscribers)
  → Preprocessing (column mapping, QC, validation)
    → Feature Engineering (47 features, 5 layers)
      → Train/Val/Test Split (70/15/15)
        → Baseline Benchmarking (6 model families)
          → Champion Selection (tolerance-band)
            → Isotonic Calibration
              → SHAP Explainability (local + global)
                → Deterministic Rules (R00–R13 + R99)
                  → FastAPI REST (20 endpoints)
                    → Next.js Dashboard (9 pages, EN/FA)
                      → CSV/Parquet BI Export
```
