/**
 * Executive Risk Tier Classification System
 *
 * Maps raw ML risk tier values from the backend to executive-facing tier
 * labels, colors, and descriptions. The system translates model output
 * tiers (Very High, High, Medium, Low) into business language that CRM
 * teams can action (Critical, At Risk, Watchlist, Stable).
 *
 * This abstraction layer:
 * 1. Preserves the original ML tier in audit contexts
 * 2. Provides executive-safe wording for dashboards and summaries
 * 3. Assigns consistent visual colors for risk tier badges
 * 4. Defines tier ordering for sorting and prioritization
 *
 * Tier definitions:
 * - Critical (Very High): High probability of churn — immediate retention action
 * - At Risk (High): Elevated churn risk — prioritize for intervention
 * - Watchlist (Medium): Moderate risk indicators — monitor closely
 * - Stable (Low): Low observed churn risk — standard engagement sufficient
 */

/** Canonical executive risk tier values. */
export const RISK_TIER_VALUES = {
  CRITICAL: "Critical",
  AT_RISK: "At Risk",
  WATCHLIST: "Watchlist",
  STABLE: "Stable",
} as const;

/** Maps raw ML tier labels to executive-facing labels. */
export const RISK_TIER_MAP: Record<string, string> = {
  "Very High": RISK_TIER_VALUES.CRITICAL,
  High: RISK_TIER_VALUES.AT_RISK,
  Medium: RISK_TIER_VALUES.WATCHLIST,
  Low: RISK_TIER_VALUES.STABLE,
};

/** Tailwind color classes for raw ML tier badges. */
export const RISK_TIER_COLORS: Record<string, string> = {
  "Very High": "bg-red-100 text-red-700",
  High: "bg-amber-100 text-amber-700",
  Medium: "bg-blue-100 text-blue-700",
  Low: "bg-emerald-100 text-emerald-700",
};

/** Tailwind color classes for executive tier badges. */
export const RISK_TIER_EXEC_COLORS: Record<string, string> = {
  Critical: "bg-red-100 text-red-700",
  "At Risk": "bg-amber-100 text-amber-700",
  Watchlist: "bg-blue-100 text-blue-700",
  Stable: "bg-emerald-100 text-emerald-700",
};

/** Sort order for raw ML tiers (lower = higher priority). */
export const RISK_TIER_ORDER: Record<string, number> = {
  "Very High": 0,
  High: 1,
  Medium: 2,
  Low: 3,
};

/** Maps a raw ML tier to its executive-facing label. Returns original value if unmapped. */
export function getExecutiveRiskTier(tier: string | null): string {
  if (!tier) return "—";
  return RISK_TIER_MAP[tier] || tier;
}

/** Returns ML tiers sorted by risk priority (highest first). */
export function getSortedRiskTiers(): string[] {
  return Object.keys(RISK_TIER_MAP).sort(
    (a, b) => (RISK_TIER_ORDER[a] ?? 99) - (RISK_TIER_ORDER[b] ?? 99),
  );
}

/** Executive descriptions for each raw ML tier. */
export const RISK_TIER_DESCRIPTIONS: Record<string, string> = {
  "Very High":
    "High probability of churn — immediate retention action required",
  High: "Elevated churn risk — prioritize for intervention",
  Medium: "Moderate risk indicators — monitor closely",
  Low: "Low observed churn risk — standard engagement sufficient",
};

/** Executive descriptions for each executive tier label. */
export const RISK_TIER_EXEC_DESCRIPTIONS: Record<string, string> = {
  Critical:
    "High probability of churn — immediate retention action required",
  "At Risk": "Elevated churn risk — prioritize for intervention",
  Watchlist: "Moderate risk indicators — monitor closely",
  Stable: "Low observed churn risk — standard engagement sufficient",
};

/**
 * Business-facing labels keyed by snake_case backend risk tier values.
 * Maps backend conventions to executive labels.
 */
export const RISK_TIER_BUSINESS_LABELS: Record<string, string> = {
  critical: "Critical",
  very_high: "Critical", // Both "critical" and "very_high" map to the same executive tier — the backend transitioned naming conventions but both may appear in historical data
  high: "At Risk",
  medium: "Watchlist",
  low: "Stable",
};

/**
 * Canonical plain-English operational descriptions for risk tiers.
 * Keyed by snake_case backend values for direct lookup.
 */
export const RISK_TIER_BUSINESS_EXPLANATIONS: Record<string, string> = {
  critical: "Immediate retention intervention required — highest churn probability subscribers.",
  very_high: "Immediate retention intervention required — highest churn probability subscribers.", // Duplicated for the same naming-evolution reason as RISK_TIER_BUSINESS_LABELS
  high: "High churn probability — prioritized for proactive retention outreach and high-value offers.",
  medium: "Moderate churn risk — monitor for escalation indicators; standard retention cycle applies.",
  low: "Low churn risk — standard retention cycle; no immediate intervention needed.",
};

/** Resolves a backend risk tier key (snake_case) to a business-facing label. */
export function getRiskTierLabel(tier: string): string {
  return RISK_TIER_BUSINESS_LABELS[tier] || tier.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Returns a plain-English operational description for a risk tier. */
export function getRiskTierExplanation(tier: string): string {
  return RISK_TIER_BUSINESS_EXPLANATIONS[tier] || "";
}
