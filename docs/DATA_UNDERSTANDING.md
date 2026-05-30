# Data Understanding & Initial Ingestion

**Dataset:** `MCI_Challenge_FinalDataset.csv`  
**Artifacts:** `data/schema/data_dictionary.json`, `data/schema/column_profile.json`  
**Regenerate profile:** `python scripts/profile_raw_data.py`

---

## 1. Summary of dataset structure

| Item | Verified value |
|------|----------------|
| Rows | **7,043** |
| Columns | **17** |
| Encoding | **UTF-8** (Persian labels and values) |
| Grain | One row per subscriber |
| **Naming convention** | **Raw:** Persian headers as in file (ZWNJ stripped on load). **Standard:** English `snake_case` business names in `data_dictionary.json` — all downstream pipelines use English only. |
| Primary key | `subscriber_id` / `شناسه_مشترک` — **7,043 unique**, range 1–7043 (anonymized index, not MSISDN) |
| Target | `churn_label` / `ریزش` — binary **`بله`** (churn) / **`خیر`** (retained) |
| Churn rate | **26.54%** (1,869 / 7,043) |

---

## 2. Data dictionary (machine-readable)

Full spec: **`data/schema/data_dictionary.json`** includes:

- `standard_name`, `raw_name`, `role`, `dtype`
- `allowed_values` per categorical
- Numeric min / max / mean / median
- `structural_missingness` rule for 2G
- `leakage_warnings` and `known_ambiguities`
- **`data_quality_gates`** (must-pass vs allowed-unresolved vs block)

Column-level profiling (counts, all categories): **`data/schema/column_profile.json`**

---

## 3. Column mapping (business → dataset)

| Business theme | Standard name | Raw name |
|----------------|---------------|----------|
| Churn (target) | `churn_label` | `ریزش` |
| SIM type | `sim_card_type` | `نوع_سیم‌کارت` |
| Payment | `monthly_spend_toman`, `cumulative_spend_toman` | `هزینه_ماهیانه_تومان`, `هزینه_کل_تومان` |
| Tenure | `sim_tenure_months` | `سابقه_سیم‌کارت_ماه` |
| Internet generation | `mobile_data_generation` | `نسل_اینترنت_همراه` |
| VAS | roaming, cloud, night, superapps | six service columns |
| VoLTE | `volte_service` | `سرویس_تماس_VoLTE` |
| App engagement | `operator_app_usage` | `استفاده_اپلیکیشن_اپراتور` |
| Demographics | `gender`, `age`, `birth_month_persian` | `جنسیت`, `سن`, `ماه_تولد` |

**Not in file:** region, city, usage volume (min/SMS/GB), NPS, campaign history.

---

## 4. Data quality — verification evidence

### 4.1 Missing values (beyond `NaN`)

| Check | Result |
|-------|--------|
| Pandas `NaN` | **0** in all 17 columns |
| Blank strings (`""` or whitespace-only) | **0** |
| Placeholder tokens (`NA`, `N/A`, `ندارد`, `-`, `null`, etc.) | **0** |
| Hidden non-numeric in numeric columns | **None** — `int64` parses cleanly |

### 4.2 Duplicates & keys

| Check | Result |
|-------|--------|
| Duplicate rows | **0** |
| Duplicate `subscriber_id` | **0** |

### 4.3 Numeric profiling

| Column | Min | Max | Mean | Median |
|--------|-----|-----|------|--------|
| `age` | 18 | 75 | 40.07 | 40 |
| `sim_tenure_months` | **0** | 72 | 32.37 | 29 |
| `monthly_spend_toman` | 2,737,500 | 17,812,500 | 9,714,254 | 10,552,500 |
| `cumulative_spend_toman` | **0** | 1,302,720,000 | 341,960,144 | 209,182,500 |

### 4.4 Categorical inventory (complete)

| Column | Unique | Allowed values (verified) |
|--------|--------|---------------------------|
| `gender` | 2 | مرد (3,555), زن (3,488) |
| `birth_month_persian` | 12 | All Persian months present (~564–640 each) |
| `mobile_data_generation` | 4 | 5G (3,096), 4G (1,695), 2G (1,526), 3G (726) |
| Service columns (×6) | 3 each | بله, خیر, **فاقد سرویس دیتا** |
| `sim_card_type` | 2 | اعتباری/prepaid (3,875), دائمی/postpaid (3,168) |
| `operator_app_usage` | 2 | بله (4,171), خیر (2,872) |
| `churn_label` | 2 | خیر (5,174), بله (1,869) |

### 4.5 Structural missingness (2G) — **not optional QC**

For **`mobile_data_generation == "2G"`** (n = **1,526**, 21.7%):

- All six data-dependent service columns are **100% `فاقد سرویس دیتا`**
- **Rule:** Treat as **`not_applicable`**, **not** as “customer declined service” (do not map to `خیر` without `is_data_capable` flag)

### 4.6 High-severity ambiguity: tenure = 0 vs spend

**11 subscribers** match:

| Pattern | Count |
|---------|-------|
| `sim_tenure_months == 0` | 11 |
| `cumulative_spend_toman == 0` | 11 (same rows) |
| `monthly_spend_toman > 0` | 11 |

**Interpretation (must confirm with business):**

- “Monthly” may mean **current plan rate** or **in-month observed spend** while tenure counter is still zero at snapshot.
- **Not safe** to treat `cumulative` as `monthly × tenure` for these rows or globally.

**Preprocessing policy:** **do not impute** spend; set `tenure_zero_flag` and `billing_definition_ambiguous_flag` instead.

### 4.7 Cumulative vs monthly × tenure — **do not assume identity**

| Metric | Value |
|--------|-------|
| Rows where `cumulative == monthly × tenure` | **625 (8.87%)** |

**Implication:** Fields likely use **different billing windows or horizons**. Do **not** create `lifetime_spend = monthly × tenure` as truth; any ratio features need **explicit business sign-off** and **leakage review** (see below).

---

## 5. Leakage warnings

| Field | Risk | Required before modeling |
|-------|------|-------------------------|
| `cumulative_spend_toman` | May aggregate spend over a period that overlaps or follows churn decision | Confirm label observation date vs spend window |
| `monthly_spend_toman` | Snapshot ambiguity when tenure = 0 | Confirm definition |
| `churn_label` | Must never be used to impute or clip features | Enforced in pipeline |

---

## 6. Data quality gates (preprocessing readiness)

### Must pass (verified ✓)

- [x] 7,043 rows, 17 columns  
- [x] Unique `subscriber_id`, zero duplicate rows  
- [x] Target ∈ {بله, خیر} only  
- [x] No NaN, blank, or placeholder strings  
- [x] All categoricals ⊆ documented `allowed_values`  
- [x] Numeric fields valid `int64`  

### Allowed unresolved (documented, proceed with rules)

- [ ] Business definition of **tenure = 0 + positive monthly** (interim rule in preprocessing)  
- [ ] **Churn label horizon** (e.g. next 30/90 days) — state assumption in model card  
- [ ] **Cumulative vs monthly** relationship — no derived identity without formula  

### Block preprocessing if

- New unexpected category values appear on re-ingest  
- Duplicate IDs or new NaN/blank strings detected  

---

## 7. Ingestion workflow (reproducible)

1. Read CSV `encoding=utf-8`  
2. Normalize headers: strip, remove ZWNJ (`U+200C`) / ZWJ (`U+200D`)  
3. Validate against `data_dictionary.json` `allowed_values`  
4. Run `scripts/profile_raw_data.py` → refresh `column_profile.json`  
5. Copy raw snapshot to `data/raw/` (preprocessing pipeline)  
6. Log row count + file hash in manifest  

---

## 8. What to send before / during preprocessing review

1. Confirmation of **churn label horizon** and **spend field definitions** (especially tenure=0).  
2. Approval of **2G `not_applicable`** handling (`فاقد سرویس دیتا` → `no_data_service`, not `no`).  
3. Sign-off on **leakage stance** for `cumulative_spend_toman` in features.  

---

*Revision incorporates reviewer feedback: extended missing checks, schema artifacts, quality gates, sharper tenure/spend flags, and explicit non-identity of spend fields.*
