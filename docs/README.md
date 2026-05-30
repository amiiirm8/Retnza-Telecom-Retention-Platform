# Retnza — Technical Documentation Index

This directory contains detailed technical documentation for the Retnza telecom retention intelligence platform. Each document covers a specific pipeline stage or architectural concern.

## Pipeline Stages

| Document | Covers |
|----------|--------|
| [Data Understanding](DATA_UNDERSTANDING.md) | Raw data schema, column semantics, quality observations, bilingual token mapping |
| [Data Preprocessing](DATA_PREPROCESSING.md) | Cleaning pipeline: column mapping, QC, validation, canonical export |
| [Exploratory Analysis](EXPLORATORY_ANALYSIS.md) | EDA methodology, churn rate patterns, segment comparisons, key findings |
| [Signal Engineering](SIGNAL_ENGINEERING.md) | Feature construction: 47 features across 5 conceptual layers |
| [Baseline Modeling](BASELINE_MODELING.md) | Model benchmarking, imbalance strategies, threshold policies, champion selection |
| [Champion Model](CHAMPION_MODEL.md) | Final model architecture, calibration, operating threshold, performance summary |
| [Explainability & Recommendations](EXPLAINABILITY_RECOMMENDATIONS.md) | SHAP driver analysis, 15 rule IDs (R00–R13 + R99), retention play catalog |
| [Recommendation Engine](RECOMMENDATION_ENGINE.md) | Rule design, precedence, channel resolution, campaign costing |
| [Behavioral Segmentation](BEHAVIORAL_SEGMENTATION.md) | K-Means clustering (3 segments), stability analysis, operational profiles |

## Architecture & Operations

| Document | Covers |
|----------|--------|
| [Platform Architecture](PLATFORM_ARCHITECTURE.md) | System overview, data flow, component interactions, deployment topology |
| [Business Intelligence](BUSINESS_INTELLIGENCE.md) | BI export layer, Power BI integration, CRM-ready datasets |
| [Migration & Bootstrap](MIGRATION_AND_BOOTSTRAP.md) | Database migrations, Alembic configuration, schema versioning |

## Quick Reference

- **Model features:** 47 (5 conceptual layers)
- **Recommendation rules:** 14 business rules + R99 fallback (15 rule IDs)
- **Dashboard pages:** 9 (bilingual EN/FA)
- **API endpoints:** 20 REST
- **Frontend tests:** 169
- **Backend tests:** 39 (5 suites)
