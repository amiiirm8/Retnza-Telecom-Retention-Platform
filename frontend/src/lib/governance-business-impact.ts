/**
 * Retention Strategy Business Impact Computation
 *
 * Translates model performance metrics (recall, precision, false negative rate,
 * base rate, lift) into actionable business impact estimates for CRM retention
 * operations. This bridges the gap between technical model metrics and the
 * operational questions executives care about:
 *
 * - How many churners will we capture at this threshold?
 * - How many will we miss?
 * - How many loyal customers will be contacted unnecessarily?
 * - What does this mean for our CRM team's workload?
 * - How aggressive is this strategy compared to alternatives?
 *
 * The computation is role-aware — each strategy type (primary operating, reference
 * baseline, contact budget proxy) carries different operational assumptions and
 * staffing implications.
 */

/** Core validation/test metrics from a threshold policy. */
export interface PolicyMetrics {
  precision: number;
  recall: number;
  f1: number;
  false_negative_rate: number;
  lift_at_threshold: number;
  base_rate: number;
}

/** Business impact estimates derived from policy metrics. */
export interface BusinessImpact {
  /** Percentage of actual churners correctly identified */
  capturedChurnersPct: number;
  /** Percentage of actual churners missed by the threshold */
  missedChurnersPct: number;
  /** Percentage of flagged subscribers who were not actual churners */
  falseAlarmsPct: number;
  /** Raw aggressiveness score (recall / (1 - precision)) */
  aggressivenessScore: number;
  /** Human-readable aggressiveness label with operational meaning */
  aggressivenessLabel: string;
  /** Campaign workload factor (recall / precision) */
  campaignWorkloadFactor: number;
  /** Human-readable workload label for CRM capacity planning */
  campaignWorkloadLabel: string;
  /** CRM staffing implication text based on policy role and metrics */
  crmStaffingImplication: string;
  /** Estimated true positives per 10,000 subscribers at the given base rate */
  estimatedTruePositivesPer10k: number;
  /** Estimated missed churners per 10,000 subscribers */
  estimatedMissedPer10k: number;
  /** Estimated false alarms per 10,000 subscribers */
  estimatedFalseAlarmsPer10k: number;
}

const AGGRESSIVENESS_LABELS: Record<string, string> = {
  very_aggressive:
    "High Coverage — Catches most churners but contacts many loyal customers",
  aggressive:
    "Proactive — Strong recall focus with moderate false positives",
  balanced:
    "Balanced — Equal focus on catching churners and avoiding false alarms",
  conservative:
    "Targeted — Prioritizes precision over recall to reduce unnecessary contacts",
  very_conservative:
    "Minimal Outreach — High precision focus with low contact volume",
};

/**
 * Computes business impact estimates from policy threshold metrics.
 * The computation uses role-aware heuristics for aggressiveness classification
 * and staffing implications, derived from the recall-precision tradeoff.
 */
export function computeBusinessImpact(
  metrics: PolicyMetrics | null | undefined,
  role: string,
): BusinessImpact | null {
  if (!metrics) return null;

  const recall = metrics.recall;
  const precision = metrics.precision;
  const fnr = metrics.false_negative_rate;

  const capturedChurnersPct = recall * 100;
  const missedChurnersPct = fnr * 100;
  const falseAlarmsPct = (1 - precision) * 100;

  // Epsilon 0.001 prevents division by zero when precision = 1 (perfect precision)
  const aggressivenessScore = recall / (1 - precision + 0.001);
  let aggressivenessLabel: string;
  // Role-based overrides: these policy types have fixed operational intent regardless of score
  // contact_budget_proxy is always "conservative" because it optimizes for CRM capacity, not recall
  if (role === "contact_budget_proxy") {
    aggressivenessLabel = AGGRESSIVENESS_LABELS.conservative;
  // reference_baseline is always "very_conservative" because it's a governance benchmark, not a live threshold
  } else if (role === "reference_baseline") {
    aggressivenessLabel = AGGRESSIVENESS_LABELS.very_conservative;
  } else if (aggressivenessScore > 5) {
    aggressivenessLabel = AGGRESSIVENESS_LABELS.very_aggressive;
  } else if (aggressivenessScore > 3) {
    aggressivenessLabel = AGGRESSIVENESS_LABELS.aggressive;
  } else if (aggressivenessScore > 1.5) {
    aggressivenessLabel = AGGRESSIVENESS_LABELS.balanced;
  } else {
    aggressivenessLabel = AGGRESSIVENESS_LABELS.conservative;
  }

  // Epsilon 0.001 prevents division by zero when precision = 0
  const campaignWorkloadFactor = recall / (precision + 0.001);
  let campaignWorkloadLabel: string;
  if (campaignWorkloadFactor > 3) {
    campaignWorkloadLabel = "High — Significant CRM outreach volume expected under this strategy";
  } else if (campaignWorkloadFactor > 1.5) {
    campaignWorkloadLabel = "Moderate — Balanced CRM contact volume under this strategy";
  } else {
    campaignWorkloadLabel = "Low — Targeted outreach with minimal volume under this strategy";
  }

  let crmStaffingImplication: string;
  if (role === "primary_operating_policy") {
    crmStaffingImplication =
      "Expect higher contact volume under this strategy. Recommend allocating additional agent capacity for retention outbound campaigns.";
  } else if (role === "contact_budget_proxy") {
    crmStaffingImplication =
      "Aligned with existing contact center capacity planning. No additional staffing required for this strategy.";
  } else if (role === "reference_baseline") {
    crmStaffingImplication =
      "This strategy is a governance benchmark and is not used for live CRM operations.";
  } else {
    crmStaffingImplication =
      "Standard staffing levels apply under this strategy. Monitor contact volume against capacity thresholds.";
  }

  // Scale estimates to 10k subscribers for human-readable comparison across policies.
  // Default base rate of 3% matches the typical telecom churn baseline when data is unavailable.
  const per10k = 10000;
  const baseRate = metrics.base_rate || 0.03;
  const actualChurners = per10k * baseRate;
  const estimatedTruePositivesPer10k = Math.round(actualChurners * recall);
  const estimatedMissedPer10k = Math.round(actualChurners * fnr);
  const estimatedFlagged = per10k * recall / (precision + 0.001);
  const estimatedFalseAlarmsPer10k = Math.round(
    estimatedFlagged - estimatedTruePositivesPer10k,
  );

  return {
    capturedChurnersPct,
    missedChurnersPct,
    falseAlarmsPct,
    aggressivenessScore,
    aggressivenessLabel,
    campaignWorkloadFactor,
    campaignWorkloadLabel,
    crmStaffingImplication,
    estimatedTruePositivesPer10k,
    estimatedMissedPer10k,
    estimatedFalseAlarmsPer10k,
  };
}

/**
 * Returns a recommendation badge for a threshold policy describing its
 * production-readiness status and operational classification.
 * Used in policy comparison tables and business impact cards.
 */
export function getPolicyRecommendationBadge(role: string): {
  label: string;
  color: string;
  description: string;
} {
  const badges: Record<string, { label: string; color: string; description: string }> = {
    primary_operating_policy: {
      label: "Recommended for Operations",
      color: "bg-emerald-100 text-emerald-800 border-emerald-200",
      description:
        "This strategy is the active operating threshold for CRM retention operations.",
    },
    reference_baseline: {
      label: "Benchmark Reference",
      color: "bg-slate-100 text-slate-600 border-slate-200",
      description: "Maintained as a benchmarking reference for governance reviews. Not deployed for live decisioning.",
    },
    reference_only: {
      label: "Benchmark Reference",
      color: "bg-slate-100 text-slate-600 border-slate-200",
      description: "Secondary benchmark for retention strategy comparison. Not deployed for live decisioning.",
    },
    contact_budget_proxy: {
      label: "Capacity Planning",
      color: "bg-blue-100 text-blue-800 border-blue-200",
      description:
        "Optimized for CRM workload planning and outreach budget allocation.",
    },
  };
  return (
    badges[role] || {
      label: "Custom Strategy",
      color: "bg-slate-100 text-slate-600 border-slate-200",
      description: "Custom retention strategy configuration.",
    }
  );
}
