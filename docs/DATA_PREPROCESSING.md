# Data Cleaning & Preprocessing

**Schema version:** `preprocessing-schema`  
**Artifacts:** `data/cleaned/subscribers_cleaned.parquet`, `data/cleaned/preprocessing_manifest.json`  
**Regenerate:** `python scripts/build_datasets.py`

---

## 1. Cleaning strategy by column type

| Type | Treatment |
|------|---------------------|
| **ID** | `subscriber_id` unchanged |
| **Target** | `churn_label` → `churn_binary` (0/1); Persian label dropped |
| **Nominal** | Persian → English: gender, SIM type, tri-state services (`no` / `yes` / `no_data_service`) |
| **Binary** | `operator_app_usage` → `yes` / `no` (single column, not one-hot in cleaned layer) |
| **Numeric** | **No winsorization**, no scaling — raw observed Tomans and tenure |
| **Ordinal (derived later)** | `birth_month_persian` **kept in cleaned**; `birth_month_ordinal` created only in **modeling** transform |
| **Quality / operational flags** | See §1.1 — derived during preprocessing, not raw CRM measurements |
| **Spend ambiguity** | **No imputation** — cumulative/monthly values match raw CSV |

### 1.1 Derived operational flags (not raw measurements)

These columns are **created during preprocessing for audit and downstream logic**. They are **not** original source fields. In EDA and modeling (subsequent phases), treat them as **derived operational flags**, not as leakage-prone target proxies unless explicitly validated.

| Flag | Meaning | Intended use |
|------|---------|----------------|
| `tenure_zero_flag` | Snapshot tenure equals zero | Segmentation, filters, optional model input — documents infant-account edge cases |
| `billing_definition_ambiguous_flag` | **Data-quality flag only:** tenure 0, cumulative 0, monthly &gt; 0. Flags inconsistent billing semantics for analyst review; **not designed as a churn predictor** | QC dashboards, exclusion/sensitivity analyses; use in models only with documented rationale |
| `is_data_capable` | Non-2G (can subscribe to data/VAS in this schema) | **Modeling:** yes — as a structural segment indicator (with tri-state service fields). **Interpretation:** separates 2G “N/A” from true yes/no on VAS/VoLTE |

### Tri-state / 2G rule

`no_data_service` remains **distinct from** `no`. For 2G subscribers, six service fields stay `no_data_service` (structural N/A). `is_data_capable = 0` flags 2G.

### Birth month policy

| Field | In cleaned? | In sklearn modeling matrix? |
|-------|-------------|------------------------------|
| `birth_month_persian` | **Yes** — human-readable for reports / Power BI | **No** |
| `birth_month_ordinal` | **No** | **Yes** — derived at transform time from Persian month map |

**Reason:** Stakeholders read Persian month names; models need a consistent 1–12 ordinal without 12-way one-hot noise in the canonical table.

---

## 2. Detailed preprocessing steps

1. Load raw CSV (UTF-8), normalize headers (strip, remove ZWNJ).  
2. Rename to English `snake_case` (`data/schema/data_dictionary.json`).  
3. Map categoricals to English tokens; validate allowed values.  
4. Encode target `churn_binary`.  
5. Add quality flags (no spend edits).  
6. Write **canonical** `subscribers_cleaned.parquet` + manifest.  

**Explicitly not in preprocessing:** winsorization, `ColumnTransformer.fit`, class weights, train/test split.

---

## 3. Three-layer artifact model

| Layer | Path | Fitted? | Use |
|-------|------|---------|-----|
| **A. Canonical cleaned** | `data/cleaned/` | No | EDA, feature engineering, audit, Power BI joins |
| **B. Train-fitted preprocessors** | `modeling/feature_transform.py` + joblib saved in baseline / champion modeling | **Train split only** | Model training & honest evaluation |
| **C. Inference export** | `data/inference/` via `scripts/export_inference_features.py` | Full population | **BI / batch scoring only** — **not for test metrics** |

This removes validation/test leakage from winsor bounds and encoding statistics.

---

## 4. Final cleaned dataset schema (20 columns)

| # | Column | Type | Role |
|---|--------|------|------|
| 1 | `subscriber_id` | int64 | id |
| 2 | `gender` | string | feature |
| 3 | `age` | int64 | feature |
| 4 | `birth_month_persian` | string | feature (reporting) |
| 5 | `sim_tenure_months` | int64 | feature |
| 6 | `mobile_data_generation` | string | feature |
| 7–12 | six service columns | tri_state | feature |
| 13 | `sim_card_type` | string | feature |
| 14 | `operator_app_usage` | yes/no | feature |
| 15 | `monthly_spend_toman` | int64 | feature |
| 16 | `cumulative_spend_toman` | int64 | feature |
| 17 | `tenure_zero_flag` | int8 | quality_flag |
| 18 | `billing_definition_ambiguous_flag` | int8 | quality_flag |
| 19 | `is_data_capable` | int8 | feature |
| 20 | `churn_binary` | int8 | target |

**Ambiguous billing rows:** 11 (`billing_definition_ambiguous_flag = 1`).  
**Verified:** those rows still have `cumulative_spend_toman = 0` and `monthly_spend_toman > 0`.

---

## 5. Sklearn modeling matrix (baseline+, not preprocessing)

**Input columns to `ColumnTransformer` (18 logical fields):**

```
age, sim_tenure_months, monthly_spend_toman, cumulative_spend_toman,
tenure_zero_flag, billing_definition_ambiguous_flag, is_data_capable,
operator_app_user, mobile_data_generation, birth_month_ordinal,
gender, sim_card_type,
intl_roaming_package, operator_cloud_storage, night_data_package,
volte_service, superapp_social, superapp_financial
```

**`operator_app_user`:** single binary (0/1) in the numeric block — **not** two-column one-hot.

**After transform (example, full-population inference fit):** see `data/inference/inference_manifest.json` → `feature_names_out` (typically **29** columns). Exact names are **fit-dependent**; always read from the saved manifest after `fit_preprocessors()`.

**Example groups (from `modeling/feature_transform.py`):**

- 8 numeric (scaled): includes `operator_app_user`  
- 2 ordinal: `mobile_data_generation`, `birth_month_ordinal`  
- 19 one-hot columns across gender, SIM, and six tri-state fields  

---

## 6. Data quality checks after cleaning

| Check | Result |
|-------|--------|
| Row count | 7,043 |
| Spend imputation | **None** |
| Ambiguous rows flagged | 11 |
| `no_data_service` preserved | Yes |
| Duplicate IDs | 0 |
| Target valid | {0, 1} only |

---

## 7. Boundary: preprocessing vs later feature builders

**Preprocessing delivers only** `data/cleaned/subscribers_cleaned.parquet` (canonical base layer).

It does **not** produce:

- `feature_engineering/builders.py` outputs (feature engineering+),
- sklearn encoded matrices (`modeling/feature_transform.py`),
- or any winsorized / scaled columns.

Those live in separate paths and manifests. Always join back to `subscriber_id` from cleaned when auditing lineage.

## 8. What remains for EDA+

- EDA on **cleaned** table (and flags — labeled as derived where shown).  
- Business confirmation still needed for the 11 `billing_definition_ambiguous_flag` rows before spend-ratio features.  
- Modeling (baseline+): `fit_preprocessors(train_cleaned)` on train only; optional use of flags in `feature_engineering/builders.py` with explicit documentation.

---

## Reviewer response summary

| Feedback | Action taken |
|----------|--------------|
| Remove tenure-zero spend imputation | **Removed**; flags added |
| No full-frame fit in preprocessing | **Removed** `data/modeling_ready` from preprocessing pipeline |
| Winsor in modeling only | Moved to `modeling/feature_transform.py` |
| Separate inference export | `data/inference/` + warning manifest |
| Binary app usage | `operator_app_user` single column in transform |
| Explicit feature list | `MODEL_INPUT_COLUMNS` + `feature_names_out` in inference manifest |

---

*Deprecated: `data/modeling_ready/` from preprocessing-v1 — do not use for evaluation; regenerate via inference export if needed.*
