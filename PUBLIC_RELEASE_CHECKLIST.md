# Retnza — Public Release Inventory

This document lists everything included in, excluded from, and intentionally
removed from the public GitHub release of the Retnza platform.

---

## Included in Public Release

### Source Code

| Directory | Purpose |
|-----------|---------|
| `preprocessing/` | Data cleaning, QC, validation pipeline |
| `feature_engineering/` | Feature construction (47 features, 5 conceptual layers) |
| `modeling/` | ML training, evaluation, calibration, champion selection, SHAP |
| `recommendation/` | Deterministic retention rules engine (14 rules) |
| `analytics/` | Post-pipeline analysis (executive summaries, segmentation, simulations) |
| `backend/` | FastAPI REST API (20 endpoints, JWT auth, ORM, migrations) |
| `frontend/` | Next.js 15 dashboard (9 pages, bilingual EN/FA, 169 tests) |
| `scripts/` | Pipeline orchestration scripts |
| `docker/` | Docker Compose + Dockerfiles |

### Data

| Directory | Contents |
|-----------|----------|
| `data/raw/` | Raw input CSV (dataset required separately) |
| `data/cleaned/` | Cleaned parquet (preprocessing output) |
| `data/features/` | Featured parquet + manifest |
| `data/inference/` | Inference preprocessors + features |
| `data/schema/` | Data dictionary + column profiles |

### Outputs (Generated ML Artifacts)

| Directory | Contents |
|-----------|----------|
| `outputs/champion/` | Champion model bundle, manifest, calibration, drift |
| `outputs/eda/` | Churn rate CSVs, metrics, QC summaries |
| `outputs/explainability/` | SHAP values, global importance, manifest |
| `outputs/recommendations/` | Per-subscriber recommendations |
| `outputs/analytics/` | Executive summaries, segments, simulation, governance |
| `outputs/powerbi/` | CRM-ready CSV export + manifest |
| `outputs/preprocessing/` | Validation reports, QC summaries |
| `outputs/features/` | Feature summary manifest |
| `outputs/baselines/` | Baseline model comparison results |
| `outputs/dashboard/` | Pre-computed dashboard data |

### Documentation

| File | Purpose |
|------|---------|
| `README.md` | Project overview (public entry point) |
| `README_EN.md` | Full English documentation |
| `README_FA.md` | Full Persian documentation |
| `FINAL_REPORT_EN.md` | English final report |
| `FINAL_REPORT_FA.md` | Persian final report |
| `EXECUTIVE_SUMMARY_EN.md` | English executive summary |
| `EXECUTIVE_SUMMARY_FA.md` | Persian executive summary |
| `REPRODUCTION_GUIDE.md` | Reproduction instructions |
| `PUBLIC_RELEASE_CHECKLIST.md` | This file |
| `LICENSE` | MIT License |
| `docs/README.md` | Technical documentation index |
| `docs/PLATFORM_ARCHITECTURE.md` | System architecture |
| `docs/DATA_UNDERSTANDING.md` | Data understanding |
| `docs/DATA_PREPROCESSING.md` | Data preprocessing |
| `docs/EXPLORATORY_ANALYSIS.md` | Exploratory analysis |
| `docs/SIGNAL_ENGINEERING.md` | Signal/feature engineering |
| `docs/BASELINE_MODELING.md` | Baseline models |
| `docs/CHAMPION_MODEL.md` | Champion model details |
| `docs/EXPLAINABILITY_RECOMMENDATIONS.md` | Explainability + rules |
| `docs/RECOMMENDATION_ENGINE.md` | Recommendation engine |
| `docs/BEHAVIORAL_SEGMENTATION.md` | Behavioral segmentation |
| `docs/BUSINESS_INTELLIGENCE.md` | BI export layer |
| `docs/MIGRATION_AND_BOOTSTRAP.md` | Database bootstrap |

### Screenshots

| File | Page |
|------|------|
| `screenshots/dashboard.png` | Executive Dashboard |
| `screenshots/queue.png` | CRM Action Queue |
| `screenshots/subscriber.png` | Subscriber Intelligence |
| `screenshots/campaigns.png` | Campaign Playbook |
| `screenshots/ecosystem.png` | Ecosystem Analytics |
| `screenshots/health.png` | Model Health |
| `screenshots/model.png` | Governance Dashboard |
| `screenshots/behavioral.png` | Behavioral Segmentation |
| `screenshots/evidence.png` | Evidence & Insights |

### Config & Infrastructure

| File | Purpose |
|------|---------|
| `.gitignore` | Git exclusion rules |
| `.env.example` | Environment variable template |
| `.github/workflows/ci.yml` | CI pipeline (frontend lint + test + build) |
| `docker/docker-compose.yml` | Container orchestration |
| `backend/requirements.txt` | Backend Python dependencies |
| `requirements.txt` | ML pipeline Python dependencies |
| `frontend/package.json` | Frontend Node dependencies |

---

## Excluded from Public Release

### Intentionally Removed (Internal / Hackathon-Only Files)

These files were removed from the public tree because they contain
internal-only content (demo scripts, review notes, submission checklists):

| File | Reason |
|------|--------|
| `DEMO_SCRIPT.md` | Judge-facing live demo script |
| `scripts/demo_script_fa.md` | Persian demo script |
| `SUBMISSION_CHECKLIST.md` | Internal submission readiness checklist |
| `REVIEW_REPORT.md` | Internal engineering review report |
| `PRODUCTION_READINESS_REPORT.md` | Internal audit with judge-facing language |
| `DELIVERY_INVENTORY.md` | Submission delivery inventory (superseded by this file) |

### Excluded via `.gitignore`

These files and directories are excluded from git tracking via `.gitignore`
and `frontend/.gitignore`:

| Pattern / Path | Reason |
|----------------|--------|
| `__pycache__/` | Python bytecode cache |
| `*.pyc`, `*.pyo`, `*.pyd` | Compiled Python files |
| `.pytest_cache/` | Pytest cache |
| `.ruff_cache/` | Ruff linter cache |
| `.mypy_cache/` | MyPy cache |
| `.coverage`, `htmlcov/`, `coverage/` | Test coverage data |
| `.venv/`, `venv/`, `env/`, `virtualenv/` | Virtual environments |
| `node_modules/`, `frontend/node_modules/` | NPM dependencies |
| `frontend/.next/`, `frontend/out/`, `frontend/build/` | Build output |
| `*.tsbuildinfo` | TypeScript incremental build cache |
| `frontend/next-env.d.ts` | Auto-generated Next.js types |
| `.DS_Store` | macOS metadata |
| `Thumbs.db` | Windows thumbnail cache |
| `.idea/`, `.vscode/`, `.cursor/`, `.ropeproject/` | IDE config |
| `.env`, `.env.local` | Environment variables with secrets |
| `*.log` | Application logs |
| `docker/data/` | Local PostgreSQL data volume |
| `frontend/.env*` (via frontend/.gitignore) | Frontend env files |

---

## What New Users Need to Run the Project

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for PostgreSQL and Redis)
- 4 GB free disk space for ML artifacts

### Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-org/Retnza-Telecom-Retention-Platform.git
cd Retnza-Telecom-Retention-Platform

# 2. Run the full ML pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Place dataset in data/raw/, then:
python scripts/build_datasets.py
python scripts/build_features.py
python scripts/train_champion.py
python scripts/generate_recommendations.py
python scripts/export_powerbi_dataset.py

# 3. Start the platform
docker compose -f docker/docker-compose.yml up postgres redis -d
pip install -r backend/requirements.txt
python backend/scripts/seed_db.py
cd backend && uvicorn app.main:app --reload --port 8000

# 4. Start frontend (in another terminal)
cd frontend && npm install && npm run dev
```

Then visit http://localhost:3000 (login: `admin@retnza.local` / `admin123`).

---

## Notes

- The raw dataset (`MCI_Challenge_FinalDataset.csv`) is **not redistributed**.
  Users must obtain it separately.
- The removed internal files remain in git history but are not present in the
  current working tree.
- All screenshots are included to help public users evaluate the UI without
  running the full stack.
