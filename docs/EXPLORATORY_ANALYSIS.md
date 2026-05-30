# Exploratory Data Analysis & Hypothesis Testing

**Base table:** `data/cleaned/subscribers_cleaned.parquet` (7,043 rows, after preprocessing)  
**Scope:** Association-focused EDA and hypothesis screening only — **no modeling, no feature engineering, no causality claims.**

---

## 1. EDA objectives

| Objective | Success criterion |
|-----------|-----------------|
| Profile churn vs product, spend, tenure, VAS | Segment churn rates with **n** reported |
| Test business hypotheses | Pre-specified tests + **effect size** (not p-values alone) |
| Respect structural missingness | `no_data_service` / `is_data_capable` as **filters**, not “declined product” |
| Separate strong vs confounded vs weak signals | Tiered insight table for feature engineering |
| Feed feature engineering design | Document what is **safe to engineer** vs **segment markers** |

### Exploratory testing policy (multiple comparisons)

Many χ² and rank tests were run across segments and products. These are **exploratory hypothesis screens**, not confirmatory trials. **Because multiple hypotheses were tested, results are interpreted primarily by effect size (lift, Cramér’s V, Spearman ρ), stability across related cuts, and business plausibility — not p-value alone.** A p &lt; 0.05 finding with tiny effect size is deprioritized; a large lift with plausible mechanism is prioritized even if not the smallest p-value.

### Screening thresholds (decision aids, not laws)

Rules such as **p &lt; 0.05** or **Cramér’s V ≥ 0.1** are used as **practical screening aids for prioritization**, not universal truth. Final narrative weight goes to **segment size, lift magnitude, and confounding structure**.

---

## 2. Key churn hypotheses

| ID | Question | Test / view | Screening rule |
|----|----------|-------------|----------------|
| H1 | Prepaid vs postpaid churn? | χ², churn rate by `sim_card_type` | Large lift + V |
| H2 | Shorter tenure → higher churn? | Tenure bands, Spearman ρ | Monotonic churn vs shorter tenure |
| H3 | Higher monthly spend → higher churn? | Quartiles, Mann–Whitney | Positive association; **confounded** |
| H4 | Generation alone drives churn? | Churn by `mobile_data_generation` | **Must stratify by SIM** |
| H5 | VoLTE non-use among data-capable? | Filter `is_data_capable==1` | Compare yes/no only |
| H6 | VAS breadth | `vas` yes-count among capable | Gradient, not causal |
| H7 | App usage | Churn by `operator_app_usage` | **Segment marker warning** |
| H8 | Age / gender | χ² / Mann–Whitney | Weak → deprioritize |
| H9 | Birth month | χ² across 12 months | **Exploratory appendix only** |

---

## 3. Structural filter: `is_data_capable` (not an EDA “driver”)

`is_data_capable = 0` identifies **2G / voice-centric** subscribers (n = 1,526). In EDA narrative this is a **structural segment filter**, not a standalone churn “predictor.”

- Among 2G, six service fields are **always** `no_data_service` (deterministic).
- VAS/VoLTE “no vs yes” comparisons apply only where **`is_data_capable == 1`**.
- Do **not** interpret low 2G churn as “2G protects customers” without prepaid/postpaid mix context (2G is often postpaid-heavy).

---

## 4. Evidence table (compact)

Overall churn rate: **26.54%** (1,869 / 7,043).  
`billing_definition_ambiguous_flag`: **11 rows** — excluded from spend-ratio narratives or shown separately (QC cohort).

| Segment / variable | n | Churn rate | Lift vs 26.5% | Effect / test | Strength | Business interpretation (association) |
|--------------------|---|------------|---------------|---------------|----------|--------------------------------------|
| **Prepaid** | 3,875 | **42.7%** | 1.61× | V ≈ 0.41 | **Very strong** | Primary commercial segment at risk |
| **Postpaid** | 3,168 | **6.8%** | 0.25× | — | **Very strong** | Stable core; different playbook |
| **Tenure 0–6 mo** | 1,481 | **52.9%** | 2.0× | ρ ≈ −0.37 tenure | **Very strong** | Infant / early-life churn |
| **Tenure 61+ mo** | 1,407 | **6.6%** | 0.25× | — | **Very strong** | Loyalty / tenure protective association |
| **Prepaid + 5G** | 2,128 | **54.6%** | 2.06× | — | **Very strong** | High-risk product mix marker |
| **5G (unstratified)** | 3,096 | **41.9%** | 1.58× | Confounded | **Segment marker** | Cannot separate from prepaid mix |
| **2G (structural)** | 1,526 | **7.4%** | 0.28× | Filter | **Context** | Legacy segment; not comparable to VAS “no” |
| **VoLTE no (capable only)** | 3,473 | **41.6%** | 1.57× | — | **Strong** | Non-adoption among data users |
| **VoLTE yes (capable)** | 2,044 | **15.2%** | 0.57× | — | — | Adoption associated with lower churn |
| **High monthly quartile** | 1,758 | **37.5%** | 1.41× | ρ ≈ +0.18 | **Moderate** | See spend caution §5 |
| **App usage = yes** | 4,171 | **33.6%** | 1.26× | Confounded | **Segment marker** | Higher churn with app — prepaid/digital mix |
| **Super-app / weak VAS gap** | — | ~3–4 pp | ~1.1× | Small | **Weak** | Not campaign-primary |
| **Gender / age** | — | ~26–27% | ~1.0× | NS | **None** | Do not segment on these |
| **Birth month** | 564–640 / mo | 20–32% spread | — | χ² p≈0.005 | **Weak / exploratory** | **Not a driver; no campaign logic** |

---

## 5. Confounding: segment markers vs standalone levers

Several variables are **entangled** in this snapshot:

```text
prepaid  ↔  short tenure  ↔  5G  ↔  higher monthly spend  ↔  app usage
```

**EDA implication:** Some apparent “drivers” are **segment markers** (who the customer is), not independent levers (what you can pull to change outcomes).

| Variable | Verdict |
|----------|---------|
| Prepaid, short tenure | **Core segment story** — credible prioritization |
| **5G (unstratified)** | **Marker** of prepaid-heavy mix — do not say “5G causes churn” |
| **App usage = yes** | **Marker** of digital/prepaid profile — not proof that “more app = retention” |
| VoLTE / VAS (among capable) | **Behavioral adoption** signals — plausible intervention targets, still associational |
| Monthly / cumulative spend | **Tied to tenure and segment** — interpret as bill level / lifecycle, not isolated causal bill |

**Required charts for report:** churn by **generation × SIM type** (faceted), not generation alone.

---

## 6. Spend variables — extra caution

| Finding | Wording to use | Wording to avoid |
|---------|----------------|------------------|
| Higher **monthly** spend ↔ higher churn (ρ ≈ +0.18) | “Higher monthly spend is **associated with** churn in this snapshot” | “High spend **causes** churn” |
| Lower **cumulative** ↔ higher churn (short tenure) | “Low cumulative spend **co-occurs with** short tenure and higher churn” | “Low lifetime value **causes** exit” |

**Plausible mechanisms (hypotheses, not proven):** bill shock, prepaid recharge volatility, product/plan mismatch — not a single cause.

**Visualization recommendation:**

- Raw Tomans distributions (often skewed).
- **log1p(monthly_spend)** or percentile bands for charts shown to executives.
- Do **not** winsorize in EDA tables (preprocessing leaves spend observed); log views are **visualization-only** for EDA.

---

## 7. Birth month — appendix only

- **Do not** present birth month as a real churn driver in the executive storyline.
- χ² may be significant with ~12 pp spread across months, but effect is **small vs prepaid/tenure**.
- **Do not** build campaign logic on birth month.
- Optional appendix chart only, labeled **“exploratory — not actionable.”**

---

## 8. Chart & test plan (unchanged core, refined labels)

| Priority | Chart | Notes |
|----------|-------|-------|
| P0 | Churn by SIM type | n + rate on chart |
| P0 | Churn by tenure band | Derived bands 0–6, 7–12, … |
| P0 | Churn by generation **× SIM** | Confounding control |
| P1 | Monthly spend: raw + log-scale histogram by churn | Skew awareness |
| P1 | VAS/VoLTE among **data-capable only** | After structural filter |
| P2 | App usage with SIM facet | Show marker effect |
| — | Birth month | Appendix only |

---

## 9. What EDA strongly suggests vs what EDA cannot prove

### EDA strongly suggests (association, prioritization for feature engineering)

1. **Prepaid** and **short tenure** are the dominant churn-associated segments.  
2. **Prepaid on 5G** is a high-risk **product mix marker**.  
3. Among **data-capable** subscribers, **low VAS adoption** and **VoLTE non-use** align with higher churn.  
4. **Gender and age** are not useful differentiators in this dataset.  
5. Spend level adds signal but is **not interpretable in isolation** from tenure/SIM.

### EDA cannot prove

1. **Causality** — any intervention (VoLTE push, VAS bundle) may not reduce churn until A/B tested.  
2. **Independent effect of 5G or app usage** — likely **segment composition**.  
3. **Optimal threshold** for “high risk” — requires modeling and calibration (Tasks 5–6).  
4. **Birth month seasonality** as a retention lever.  
5. **Safe use of cumulative spend** without business confirmation of label horizon (leakage risk).

---

## 10. Feature engineering handoff

| EDA signal | Feature engineering guidance |
|------------|-----------------|
| Prepaid, tenure, prepaid×5G | Engineer explicit flags; document as segment markers |
| VAS / VoLTE among capable | Counts and non-adopter flags; use with `is_data_capable` |
| Spend | Ratios only with tenure guards; respect ambiguous 11 rows |
| `billing_definition_ambiguous_flag` | QC / sensitivity, not a designed predictor |
| Gender, age, birth month | Omit or lowest priority |
| App usage | Include if modeling needs accuracy; **do not** market as loyalty proxy |

---

## 11. Risks & caveats (summary)

- Cross-sectional snapshot — no time-to-churn.  
- Multiple exploratory tests — emphasize effect size.  
- Simpson’s paradox on app and 5G — stratify in all stakeholder charts.  
- `no_data_service` ≠ opted out.  
- 11 ambiguous billing rows — flag only, do not over-interpret.

---

**Status:** Approved for feature engineering (with refinements above incorporated).  
**Artifacts:** Segment stats in this doc; optional exports `outputs/eda/` can be added in a future pass.

*Revision addresses reviewer feedback: multiple-testing policy, confounding/segment markers, threshold wording, spend caution, birth month stance, evidence table, EDA-vs-proof section, `is_data_capable` as structural filter.*
