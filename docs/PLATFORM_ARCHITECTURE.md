# Retnza Platform Architecture

## Overview

Retnza is a **telecom retention intelligence platform** wrapping the ML pipeline (Random Forest + isotonic calibration + SHAP + rule engine) with a **FastAPI** backend and **Next.js** operational dashboard. The business intelligence layer is delivered as an interactive web application — no Power BI dependency.

```
┌─────────────┐     JWT      ┌──────────────┐     asyncpg    ┌────────────┐
│  Next.js    │ ───────────► │   FastAPI    │ ─────────────► │ PostgreSQL │
│  Dashboard  │              │   API v1     │                │  + Redis   │
└─────────────┘              └──────┬───────┘                └────────────┘
                                    │
                                    ▼
                           joblib engine + repo
                           feature_engineering/
                           recommendation/
```

## Business Intelligence Strategy

The platform satisfies the BI/dashboard requirement through two complementary channels:

### Primary: Interactive Web Dashboard (Next.js)
The frontend provides the operational dashboard layer with:
- Executive KPI dashboard for at-a-glance business metrics
- CRM Action Queue for subscriber triage and prioritisation
- Campaign playbook for retention strategy planning
- Ecosystem analytics for adoption opportunity identification
- Model operations health monitoring
- Governance and system alignment verification

This approach was chosen over a standalone BI tool because:
- Real-time interactivity for subscriber-level triage and drill-down
- Integrated decision support (recommendations, risk drivers, campaign assignment)
- Bilingual (EN/FA) executive interface with RTL support
- No additional BI licensing or infrastructure required

### Secondary: Structured Data Export
For downstream BI/CRM integration, structured datasets are exported:
- `outputs/powerbi/crm_action_queue.csv` — full action queue for Power BI
- `outputs/dashboard/` — Parquet/JSON datasets for analytics tools
- Export script: `scripts/export_powerbi_dataset.py`

Power BI is treated as a downstream-compatible consumer of exported data, not the primary presentation surface.

## Monorepo layout

```
hacketon/
├── backend/           # FastAPI, SQLAlchemy, Alembic
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   ├── core/      # config, security, deps
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/  # ml_service, dashboard, reports
│   ├── alembic/
│   └── scripts/seed_db.py
├── frontend/          # Next.js 15 App Router — operational dashboard
├── docker/
├── docs/
├── modeling/          # ML pipeline (unchanged contract)
├── recommendation/    # Retention decision engine
└── outputs/           # Intelligence artifacts + exports
```

## Database schema

| Table | Purpose |
|-------|---------|
| `subscribers` | Profile + actual churn snapshot |
| `churn_predictions` | Versioned risk scores |
| `recommendations` | Action queue row per subscriber |
| `shap_explanations` | Business-friendly driver JSON |
| `campaign_history` | Future outbound audit |
| `model_versions` | Active engine metadata |
| `users` | JWT auth (admin/user) |
| `audit_logs` | API audit trail |

Indexes on `subscriber_id`, `risk_tier`, `campaign_priority`, `campaign_queue_rank`.

## API surface (`/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | JWT token |
| GET | `/auth/me` | Current user |
| POST | `/predict` | Live feature scoring |
| POST | `/batch-score` | CSV/parquet upload |
| GET | `/subscriber/{id}` | Full profile |
| GET | `/recommendations` | Paginated action queue |
| GET | `/dashboard/kpis` | Executive KPIs |
| GET | `/dashboard/charts` | Chart series |
| GET | `/shap/{id}` | Risk driver payload |
| GET | `/model/monitoring` | Calibration metrics |
| GET | `/reports/export/csv` | CRM export |
| GET | `/reports/export/pdf` | Campaign summary PDF |

## Scoring path

```python
p_raw = predict_raw_proba(bundle, X)
p_cal = calibrate_raw_proba(bundle, p_raw)
```

## Security

- JWT (HS256), roles: `admin`, `user`
- CORS for Next.js origin
- slowapi rate limiting on `/health` and global default
- Protected routes require `Authorization: Bearer`

## Frontend pages

| Route | Audience | Description |
|-------|----------|-------------|
| `/dashboard` | Executive | KPI dashboard — business overview, risk landscape, retention plays |
| `/queue` | CRM Operations | **Primary ops** — CRM action queue for subscriber triage |
| `/subscribers/[id]` | Analysts | Subscriber intelligence — risk drivers, campaign assignment |
| `/campaigns` | Campaign Managers | Retention playbook — play distribution, priority mix |
| `/ecosystem` | Strategy | Ecosystem analytics — adoption gaps, retention opportunities |
| `/health` | Model Ops | Operations health — performance monitoring, drift detection |
| `/model` | Governance | Model governance — system alignment, probability reliability |

## macOS local development

```bash
# 1. Postgres + Redis
docker compose -f docker/docker-compose.yml up postgres redis -d

# 2. Backend
cp .env.example .env
cd backend && pip install -r requirements.txt
PYTHONPATH=..:../backend python backend/scripts/seed_db.py
uvicorn app.main:app --reload --app-dir backend --port 8000

# 3. Frontend
cd frontend && npm install && npm run dev
```

Login: `admin@retnza.local` / `admin123`

## Docker (full stack)

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build
```

- API: http://localhost:8000/docs  
- UI: http://localhost:3000  

## Implementation roadmap

1. ✅ Backend models + seed from parquet  
2. ✅ REST API + JWT  
3. ✅ Next.js dashboard pages  
4. ✅ Docker compose  
5. ✅ Business intelligence layer (web dashboard + structured export)  
6. 🔲 Alembic autogenerate full migration (MVP uses `create_all` in seed)  
7. 🔲 Redis cache on `/dashboard/*`  
8. 🔲 WebSocket queue refresh  
9. 🔲 Campaign history write-back from UI  

## API examples

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@retnza.local","password":"admin123"}' | jq -r .access_token)

curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/dashboard/kpis

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/recommendations?page=1&campaign_priority=P1"
```

## Known Limitations

- The dashboard does not currently support write-back to campaign history (future)
- Cache layer not yet implemented for dashboard endpoints
- The BI export dataset is a static snapshot; real-time Power BI connectivity requires direct PostgreSQL access
- Bilingual support covers English and Persian (Farsi); additional locales require i18n extension
