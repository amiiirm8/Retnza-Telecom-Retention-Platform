# Feature Engineering

**Inputs:** `data/cleaned/subscribers_cleaned.parquet`  
**Outputs:** `data/features/subscribers_featured.parquet`, `data/features/feature_manifest.json`  
**Regenerate:** `python scripts/build_features.py` or `python scripts/run_tasks_2_to_4.py`

---

## 1. Feature engineering goals

- Encode **EDA-backed segment markers** (prepaid, tenure, prepaid×5G, VAS/VoLTE among capable).
- Preserve **observed spend**; no cumulative imputation.
- Keep features **interpretable** for SHAP and business rules.
- Fit **train-only** statistics where needed (`high_monthly_spend_flag` Q75 on 70% stratified train split).

---

## 2. Feature catalog (47 model features)

| Feature | Type | Formula / logic | EDA strength | Leakage note |
|---------|------|-----------------|--------------|--------------|
| `lifetime_arpu_toman` | numeric | `cumulative_spend / max(tenure,1)` | moderate | cumulative window must be pre-churn |
| `monthly_to_lifetime_arpu_ratio` | numeric | `monthly / max(lifetime_arpu,1)` | moderate | sensitive for 11 QC rows |
| `log_monthly_spend_toman` | numeric | `log1p(monthly)` | moderate | visualization-friendly |
| `tenure_bucket` | ordinal 0–4 | cut tenure: 0–6,7–12,… | very strong | safe |
| `early_lifecycle_flag` | binary | tenure ≤ 12 | very strong | safe |
| `is_data_capable` | binary | from cleaned (2G filter) | structural | not a causal “driver” |
| `vas_adoption_count` | numeric | # VAS yes if capable else -1 | strong | among capable only |
| `zero_vas_capable_flag` | binary | capable & count==0 | strong | safe |
| `volte_non_adopter_capable` | binary | capable & volte==no | strong | safe |
| `is_prepaid` | binary | prepaid SIM | very strong | segment marker |
| `prepaid_5g_risk_flag` | binary | prepaid & 5G | very strong | segment marker |
| `high_monthly_spend_flag` | binary | monthly ≥ Q75_train | moderate | Q75 train-fitted |
| `mobile_gen_ordinal` | ordinal | 2G=0…5G=3 | confounded | use with prepaid |
| `operator_app_user` | binary | app yes | marker | not loyalty proxy |
| `gender_female`, `gender_male` | binary | one-hot gender | weak | optional drop |
| `age`, `sim_tenure_months` | numeric | raw from cleaned | tenure strong | safe |

**Note:** The actual pipeline produces **47 features across 5 layers** (numerical, ordinal, one-hot encoded, engineered boolean flags, and interaction terms). The table above lists the conceptual feature groups; the full expanded set is materialized in `feature_engineering/builders.py` and `feature_manifest.json`.

**Not in model list (kept in featured table for QC):** `billing_definition_ambiguous_flag`, `tenure_zero_flag`, `birth_month_persian`, service raw columns.

---

## 3. Safe vs cautious vs excluded

| Tier | Features |
|------|----------|
| **Safe** | tenure_bucket, early_lifecycle, is_prepaid, prepaid_5g, vas/volte flags (capable), zero_vas |
| **Cautious** | spend ratios, high_monthly_flag, mobile_gen, operator_app_user |
| **Excluded from FE** | gender/age (weak EDA), birth_month, churn_binary as feature |

---

## 4. Boundaries

| Artifact | Role |
|----------|------|
| `data/cleaned/` | Canonical base (preprocessing) |
| `data/features/` | Engineered columns + full row |
| `data/inference/` | Sklearn transform export only (not feature engineering) |

---

## 5. Validation

- Row count = 7,043  
- 11 ambiguous billing rows: cumulative still 0  
- `feature_manifest.json` lists ordered `model_feature_columns`

---

*Aligned with exploratory analysis handoff.*
