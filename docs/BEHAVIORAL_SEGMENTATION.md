# Behavioral Segmentation Layer

## Objective

Discover meaningful subscriber segments from the actual feature space using
unsupervised learning, profile them in business language, relate each segment
to churn risk, and surface them in the product.

This addresses **Objective 3** ("Analyze subscriber behavior and extract meaningful
patterns in the data") with a **data-driven segmentation layer** that goes beyond
predefined ecosystem labels and hand-crafted rules.

---

## Approach

### Data-Driven Discovery

Segments are **discovered from the data**, not predefined:

1. **Behavioral features** are selected for their relevance to usage, engagement,
   lifecycle, and spend patterns — excluding target leakage, identifiers, and
   structural flags like `is_prepaid`.
2. **Three clustering methods** are compared: K-Means, Gaussian Mixture Models,
   and Agglomerative Clustering.
3. **Optimal K** is selected by silhouette score across k=3–8.
4. **Cluster stability** is assessed across 5 random seeds using the adjusted
   Rand index (ARI).
5. **Final solution** is chosen by silhouette score (primary) and Davies-Bouldin
   index (tie-breaker).

### Selected Solution

| Property | Value |
|----------|-------|
| Method | K-Means |
| K | 3 |
| Silhouette | 0.33 |
| Davies-Bouldin | 1.18 |
| Calinski-Harabasz | 5,748 |
| Stability (ARI) | 0.999 |
| Features | 9 behavioral dimensions |

### Method Selection Rationale

K-Means was selected because it achieved the highest silhouette score (0.330)
among the three methods evaluated. GMM (0.250) was a distant competitor —
the 0.080 gap confirms K-Means as the clearly better choice for this data.
The choice is pragmatic: K-Means also offers
deterministic, reproducible results and simpler interpretability for operational
use — an important consideration for operational and CRM deployment contexts.

### Scientific Context

A silhouette score of 0.33 is considered **acceptable** for behavioral telecom
data, where natural cluster separation is limited due to overlapping usage
patterns across continuous dimensions. Industry literature (e.g.,
Kaufman & Rousseeuw, 1990) categorises 0.25–0.50 as "weak but realistic
structure." More important than absolute silhouette is **cluster stability**:
an ARI of 0.999 across 5 random seeds indicates the solution is highly
reproducible and not an artefact of initialisation. The Davies-Bouldin index
(1.18) and Calinski-Harabasz (5,748) are consistent with a reasonable
cluster structure on this feature set.

---

## Segments Discovered

### 1. Premium Digital Engaged (37%)

**Size:** 2,630 subscribers  
**Mean churn risk:** 25.6% (0.96× base average)  
**Observed churn rate:** 25.1%

**Characterized by:** Higher digital engagement, VAS adoption, ecosystem services,
and lifetime spend than average.

**Interpretation:** These are the most engaged subscribers — high digital activity,
broad ecosystem adoption, and above-average spend. Their churn risk is moderate
and slightly below the overall average (risk ratio 0.96×). Retention efforts
should focus on loyalty rewards, exclusive perks, and premium service upsells
rather than basic retention.

**Retention posture:** Loyalty rewards and exclusive perks; upsell premium services.

**Priority:** High — significant revenue exposure despite below-average risk.

**Channel:** Digital (preferred) with hybrid for high-value cases.

**Treatment:** Premium loyalty programme with curated offers; exclusive ecosystem
benefits; proactive upsell to higher-tier services.

### 2. Early-Life At-Risk Users (39%)

**Size:** 2,745 subscribers  
**Mean churn risk:** 38.5% (1.43× base average)  
**Observed churn rate:** 37.9%

**Characterized by:** Shorter tenure, lower digital engagement, basic ecosystem
adoption. Many are on 4G/5G networks but not using digital services.

**Interpretation:** These are newer subscribers who haven't yet adopted the
ecosystem or digital services. Despite having modern network capabilities
(4G/5G), they show low digital engagement. This is the **highest churn risk
segment** — 38.5% predicted risk vs 26.9% overall average. Early lifecycle
intervention is critical. Their churn risk ratio of 1.43× means they are
43% more likely to churn than the average subscriber.

**Retention posture:** Intensive digital onboarding with welcome campaigns and
ecosystem discovery. SMS + app-based outreach.

**Priority:** High — highest absolute and relative churn risk.

**Channel:** SMS + app-based (digital), with escalation to human touch for
high-risk cases.

**Treatment:** Welcome campaigns, ecosystem onboarding flow, targeted VoLTE
enablement, and early-lifecycle retention offers.

### 3. Low-Engagement Stable (24%)

**Size:** 1,668 subscribers  
**Mean churn risk:** 10.0% (0.37× base average)  
**Observed churn rate:** 10.0%

**Characterized by:** Below-average spend, network generation, spend intensity,
digital engagement, and ecosystem adoption.

**Interpretation:** Despite being the least engaged segment, these subscribers
have the **lowest churn risk** by a wide margin. They tend to be long-standing
subscribers with minimal service usage — "set and forget" users who are stable
but not actively engaged. Their low risk (0.37× base average) demonstrates that
low engagement alone is not a churn signal; it is the combination of low
engagement with early lifecycle that drives churn.

**Retention posture:** Standard CRM engagement; monitor for early risk signals.

**Priority:** Low — minimal churn risk; standard engagement sufficient.

**Channel:** SMS (low-cost, non-intrusive).

**Treatment:** Passive retention; periodic SMS check-ins; no aggressive offers.

---

## Key Insights

1. **Low engagement ≠ high churn.** The "Low-Engagement Stable" segment has the
   lowest churn risk (10.0% vs 26.9% average), despite having the lowest
   engagement levels. This challenges the assumption that disengaged subscribers
   are always at risk.

2. **Early lifecycle is the dominant risk factor.** The "Early-Life At-Risk Users"
   segment (39% of subscribers) has nearly 4× the churn risk of the "Low-Engagement
   Stable" segment. Short tenure with low digital adoption is the strongest
   behavioral churn signal.

3. **High engagement does not guarantee retention.** "Premium Digital Engaged"
   still shows 25.6% churn risk — significant despite being the most engaged
   cohort. Engagement alone is insufficient; targeted retention is still needed.

4. **Three clear behavioral archetypes.** The data naturally separates into
   three distinct groups: engaged/high-value (37%), new/at-risk (39%), and
   stable/low-engagement (24%).

---

## Operational Interpretation per Segment

Each profile includes an `operational_interpretation` field with plain-language
retention guidance, designed to be immediately actionable by CRM teams:

- **Premium Digital Engaged:** "These are the most engaged subscribers with
  above-average ecosystem adoption and spend. Their churn risk is slightly below
  average. Retain through loyalty rewards and premium service upsell rather than
  basic retention offers. Channel: digital preferred."

- **Early-Life At-Risk Users:** "Newer subscribers with low digital engagement
  despite modern network capabilities. This is the highest-risk segment at 1.43×
  the average churn probability. Immediate intervention needed: onboarding flows,
  ecosystem discovery, and welcome campaigns via SMS + app."

- **Low-Engagement Stable:** "Long-standing subscribers with minimal usage and
  very low churn risk (0.37× average). No aggressive retention needed. Standard
  CRM engagement and monitoring are sufficient. Channel: low-cost SMS."

---

## Limitations

1. **Descriptive, not causal.** These segments describe observed associations
   between behavioral patterns and churn risk. They do not claim that changing
   a subscriber's behavioral pattern will change their churn risk.

2. **Snapshot in time.** Segments reflect the current state of the data. As the
   subscriber base evolves, segment composition and characteristics may change.

3. **Feature-dependent.** The discovered segments depend on the selected features.
   Different feature sets would yield different groupings. The 9 behavioral
   features were chosen to capture usage, engagement, lifecycle, and spend
   dimensions while avoiding target leakage.

4. **Moderate silhouette.** A score of 0.33 is acceptable for behavioral telecom
   data but does not indicate perfectly separated clusters. The solution was
   validated by high stability (ARI > 0.99) across 5 random seeds.

5. **No temporal dimension.** Segments are computed from a single time snapshot;
   subscribers may transition between segments over time. Temporal dynamics are
   not captured.

---

## How Segments Are Computed

See `analytics/behavioral_segmentation.py` for the full implementation pipeline:

1. Load features (`subscribers_featured.parquet`) and recommendations
   (`subscriber_recommendations.parquet`).
2. Select 9 behavioral features: tenure, lifetime ARPU, log monthly spend,
   spend intensity, digital engagement, ecosystem service count, VAS adoption
   count, network generation, and age.
3. Winsorize extreme values at the 99th percentile.
4. Standardize using StandardScaler.
5. Compare K-Means, GMM, and Agglomerative clustering (k=3..8).
6. Select best method + K via silhouette score.
7. Assess cluster stability across 5 seeds (ARI).
8. Profile each cluster: distinguishing features (z-score vs global mean),
   churn risk, retention posture, and operational treatment.
9. Compute churn risk ratio (segment risk / overall average) for each profile.
10. Generate operational interpretation (plain-language retention guidance).

### Output Schema Enhancements

The summary JSON has been extended with:

| Field | Description |
|-------|-------------|
| `profiles[].churn_risk_ratio` | How many × the base average risk (e.g., 1.43 = 43% above average) |
| `profiles[].operational_interpretation` | Plain-language retention guidance for CRM teams |
| `method_selection_rationale` | Explanation of why K-Means was chosen over alternatives |
| `scientific_context` | Context for interpreting silhouette score in telecom data |
| `limitations` | Explicit list of methodological caveats |

### Output Artifacts

| Artifact | Location | Format |
|----------|----------|--------|
| Segment summary | `outputs/analytics/behavioral_segments_summary.json` | JSON |
| Cluster assignments | `outputs/dashboard/behavioral_segments.parquet` | Parquet |

---

## Product Surface

The segments are displayed on the **Behavioral Segments** page (`/behavioral-segments`)
in the Retnza dashboard:

- **Summary banner** — Methodology, metrics, and narrative.
- **Insight callout cards** — Highest-risk, lowest-risk, and overall average risk.
- **Cluster cards** — Name, size, risk, churn rate, distinguishing features, cards highlight
  risk ratio and retention posture. Click to expand for operational interpretation.
- **Charts** — Segment distribution (bar), risk comparison (bar with overall average
  reference line), feature profile radar, method comparison table.
- **Methodology section** — Scientific context, method selection rationale, feature list,
  method comparison, limitations.

Design is bilingual (EN/FA), RTL-safe, and matches the existing product visual
language.
