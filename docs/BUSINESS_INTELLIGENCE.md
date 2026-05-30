# Business Intelligence Layer

## Overview

The Retnza business intelligence (BI) requirement is delivered through two complementary channels:

1. **Primary: Interactive Web Dashboard** — the Next.js frontend serves as the operational BI layer
2. **Secondary: Structured Data Export** — for downstream Power BI / CRM integration

This document explains the BI strategy and how it satisfies the dashboard requirement.

## Why a Web-Based BI Layer?

The decision to implement BI as a web application rather than a standalone Power BI dashboard was driven by:

- **Real-time interactivity**: Subscriber-level drill-down, dynamic filtering, and live risk driver analysis require interactive capabilities beyond static BI dashboards
- **Integrated decision support**: Retention recommendations, campaign assignment, and operational guidance are embedded alongside analytics — not available in a standalone BI tool
- **Bilingual executive interface**: Full English and Persian (Farsi) support with RTL layout, localised number formatting, and culturally appropriate terminology
- **Operational workflow**: The CRM Action Queue serves as a frontline triage tool, not just a reporting surface
- **Zero additional licensing**: No Power BI licenses, infrastructure, or maintenance required

## Dashboard as BI Layer

The following pages collectively satisfy the BI requirement:

| Page | BI Function | Decision Support |
|------|-------------|-----------------|
| Executive Dashboard | KPI monitoring, risk distribution, trend analysis | "Which subscribers need immediate attention? What is the dominant churn pattern?" |
| CRM Action Queue | Operational subscriber list with filtering | "Which subscriber should I call next? What play and channel should I use?" |
| Campaign Playbook | Retention play distribution and priority mix | "Which plays are most triggered? Where should campaign budget go?" |
| Ecosystem Analytics | Segment analysis, adoption funnel, risk by segment | "Which ecosystem adoption gaps represent the biggest retention opportunity?" |
| Operations Health | Performance monitoring, drift detection | "Is the intelligence engine still reliable? Has the subscriber base shifted?" |
| Governance | System alignment, probability reliability | "Are all system components aligned? Can we trust the risk scores?" |

## Structured Data Export

For Power BI, CRM systems, and downstream analytics:

- **CSV Export**: `outputs/powerbi/crm_action_queue.csv` — full action queue with all fields
- **Parquet Datasets**: `outputs/dashboard/` — multiple structured datasets for analytics
- **Export Script**: `scripts/export_powerbi_dataset.py` — generates the export datasets

### Power BI Integration

Power BI is supported as a downstream consumer of exported data:

1. Run `scripts/export_powerbi_dataset.py` to generate the latest export
2. Import `outputs/powerbi/crm_action_queue.csv` into Power BI
3. Use `outputs/dashboard/` parquet files for additional dimensions
4. Schedule regular exports for refreshed data

For real-time Power BI connectivity, grant Power BI direct read access to the PostgreSQL database.

## Data Model for BI

The export dataset includes all fields needed for BI analysis:

| Field | Description |
|-------|-------------|
| `subscriber_id` | Unique subscriber identifier |
| `churn_probability` | Calibrated churn risk score (for CRM) |
| `churn_probability_raw` | Raw model score (for ranking) |
| `risk_tier` | Executive risk tier (Critical / At Risk / Watchlist / Stable); backend uses Very High / High / Medium / Low |
| `campaign_priority` | Campaign priority (P1–P4) |
| `rule_id` | Triggered retention rule |
| `recommended_action` | Recommended retention action |
| `final_top_driver` | Primary churn driver |
| `primary_channel` | Primary outreach channel |
| `intervention_type` | Intervention type (digital / human-touch / hybrid) |
| `ecosystem_segment` | Ecosystem segment classification |

All labels in the export use the same business terminology as the dashboard interface.

## Limitations

- Exports are static snapshots; real-time Power BI requires direct DB access
- Campaign history write-back is a planned future feature
- The dashboard does not currently support custom report authoring
