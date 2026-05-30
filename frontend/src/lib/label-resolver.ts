/**
 * Centralized Business-Label Resolution System
 *
 * Maps raw backend data codes to business-readable labels across all domains:
 * ecosystem segments, campaign priorities, communication channels, model
 * drivers, intervention types, retention strategies, and operational queues.
 *
 * Each resolver function:
 * 1. Accepts the raw code (or null/undefined)
 * 2. Looks up the business label from a typed registry
 * 3. Falls back to a humanized version of the raw code
 * 4. Returns "—" for null/undefined/missing values
 *
 * This prevents raw technical codes from appearing in the UI while preserving
 * the ability to trace back to the original backend value.
 */

// ── Ecosystem Segment Registry ──────────────────────────────────────────────

export const ECOSYSTEM_SEGMENT_LABELS: Record<string, string> = {
  non_ecosystem: "Non-Ecosystem",
  volte_only: "VoLTE Only",
  rubika_only: "Rubika Only",
  ewano_only: "EWANO Only",
  hamrahman_only: "Hamrah Man Only",
  partial_ecosystem: "Partial Ecosystem",
  fully_adopted: "Fully Embedded", // Preserved as legacy alias — the canonical key is fully_embedded
  fully_embedded: "Fully Embedded",
};

// ── Campaign Priority Registry ──────────────────────────────────────────────

export const PRIORITY_LABELS: Record<string, string> = {
  P1: "Critical Priority",
  P2: "High Priority",
  P3: "Standard Priority",
  P4: "Low Priority",
};

// ── Communication Channel Registry ──────────────────────────────────────────

export const CHANNEL_LABELS: Record<string, string> = {
  SMS: "SMS",
  Email: "Email",
  IVR: "IVR Call",
  "Push Notification": "Push Notification",
  "In-App": "In-App Message",
  "Call Center": "Call Center",
};

// ── Model Driver / Feature Registry ─────────────────────────────────────────

export const DRIVER_LABELS: Record<string, string> = {
  monthly_spend: "Monthly Spend",
  sim_tenure_months: "Tenure Duration",
  mobile_data_generation: "Network Generation",
  sim_card_type: "SIM Type",
  age: "Customer Age",
  churn_actual: "Historical Churn",
  has_rubika: "Rubika Adoption",
  has_ewano: "EWANO Adoption",
  has_hamrahman: "Hamrah Man Engagement",
  has_volte: "VoLTE Usage",
  ecosystem_product_count: "Ecosystem Product Count",
  ecosystem_engagement_level: "Ecosystem Engagement",
  ecosystem_segment: "Ecosystem Segment",
  monthly_spend_toman: "Monthly Spend (T)",
  bill_shock: "Bill Shock Indicator",
  data_usage_gb: "Data Usage (GB)",
  call_duration_min: "Call Duration (min)",
  sms_count: "SMS Volume",
};

// ── Retention Action Registry ───────────────────────────────────────────────

export const ACTION_LABELS: Record<string, string> = {
  incentivize: "Offer retention incentive — discount or bonus",
  educate: "Send educational content about product value",
  upgrade: "Recommend plan or device upgrade",
  migrate: "Migrate to modern network (4G/5G)",
  cross_sell: "Cross-sell ecosystem product",
  engage: "Increase engagement via targeted content",
  retain: "Apply standard retention treatment",
  escalate: "Escalate to human-touch retention team",
  digital_only: "Apply digital-only retention outreach",
};

// ── Operational Cost Tier Registry ──────────────────────────────────────────

export const COST_TIER_LABELS: Record<string, string> = {
  low: "Budget",
  medium: "Standard",
  high: "Premium",
};

// ── CRM Queue Registry ──────────────────────────────────────────────────────

export const CRM_QUEUE_LABELS: Record<string, string> = {
  standard: "Main Queue",
  priority: "High-Priority Queue",
  ecosystem: "Ecosystem Queue",
  retention: "Retention Queue",
  vip: "VIP Queue",
};

// ── Driver Source Registry ──────────────────────────────────────────────────

export const DRIVER_SOURCE_LABELS: Record<string, string> = {
  rule: "Rule-based",
  shap: "Model-based (SHAP)",
  rule_based: "Rule-based",
  shap_based: "Model-based (SHAP)",
};

// ── Intervention Type Registry ──────────────────────────────────────────────

export const INTERVENTION_TYPE_LABELS: Record<string, string> = {
  digital: "Digital Outreach",
  "human-touch": "Human-Touch Retention Call",
  human_touch: "Human-Touch Retention Call", // Backend may send snake_case or kebab-case depending on pipeline version — both preserved for compatibility
  hybrid: "Hybrid Outreach",
  sms: "SMS Campaign",
  call: "Retention Call",
  email: "Email Campaign",
  retainer: "Retainer Programme",
};

// ── Retention Strategy Registry ─────────────────────────────────────────────

export const RETENTION_STRATEGY_LABELS: Record<string, string> = {
  onboard: "Onboarding Programme",
  re_engage: "Re-engagement Campaign",
  ecosystem_boost: "Ecosystem Adoption Boost",
  loyalty: "Loyalty Reinforcement",
  migration: "Network Migration Support",
  save: "Win-Back Save Attempt",
  monitor: "Watch & Monitor",
};

// ── Ecosystem Engagement Level Registry ─────────────────────────────────────

export const ENGAGEMENT_LEVEL_LABELS: Record<string, string> = {
  high: "High Engagement",
  medium: "Moderate Engagement",
  low: "Low Engagement",
  none: "No Engagement",
};

// ── Resolver Functions ──────────────────────────────────────────────────────

/** Resolves an ecosystem segment code to its business label. */
export function getExecutiveEcosystemSegment(segment: string | null | undefined): string {
  if (!segment) return "—";
  return (
    ECOSYSTEM_SEGMENT_LABELS[segment] ||
    segment.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

/** Resolves a campaign priority code (P1-P4) to its business label. */
export function getExecutivePriority(priority: string | null): string {
  if (!priority) return "—";
  return PRIORITY_LABELS[priority] || priority;
}

/** Resolves a communication channel code to its business label. */
export function getExecutiveChannel(channel: string | null): string {
  if (!channel) return "—";
  return CHANNEL_LABELS[channel] || channel;
}

/**
 * Resolves a model driver/feature field name to its business label.
 *
 * Two-pass lookup: first checks the raw lowercased key (fast path for
 * underscore-delimited codes), then falls back to a lowercased lookup
 * to handle casing variations from different backend pipelines.
 */
export function getExecutiveDriver(driver: string | null): string {
  if (!driver) return "—";
  if (driver.includes("_")) {
    const lower = driver.toLowerCase();
    if (DRIVER_LABELS[lower]) return DRIVER_LABELS[lower];
  }
  return DRIVER_LABELS[driver.toLowerCase()] || driver;
}

/**
 * Resolves a full recommendation action text.
 * If the action matches a known action key, returns the business label.
 * For long text, returns as-is (likely already a descriptive sentence).
 * Falls back to scanning for partial key matches to handle prefixed/suffixed action codes.
 */
export function getFullActionText(action: string | null | undefined): string {
  if (!action) return "—";
  const lower = action.toLowerCase().trim();
  if (ACTION_LABELS[lower]) return ACTION_LABELS[lower];
  // Long strings (>80 chars) are likely human-readable descriptions, not coded keys — return as-is
  if (action.length > 80) {
    return action;
  }
  // Partial-match fallback: action may embed a known key (e.g. "cross_sell_v2" contains "cross_sell")
  const key = Object.keys(ACTION_LABELS).find((k) => lower.includes(k));
  if (key) return ACTION_LABELS[key];
  return action;
}

/** Resolves a campaign cost tier code to its business label. */
export function getCostTierLabel(tier: string | null | undefined): string {
  if (!tier) return "—";
  const lower = tier.toLowerCase();
  return COST_TIER_LABELS[lower] || tier;
}

/** Resolves a CRM queue code to its business label. */
export function getCrmQueueLabel(queue: string | null | undefined): string {
  if (!queue) return "—";
  const lower = queue.toLowerCase();
  return CRM_QUEUE_LABELS[lower] || queue;
}

/** Resolves a driver source (rule/shap) to its business label. */
export function getDriverSourceLabel(source: string | null | undefined): string {
  if (!source) return "—";
  const lower = source.toLowerCase().replace(/-/g, "_");
  return DRIVER_SOURCE_LABELS[lower] || source;
}

/** Resolves an intervention type code to its business label. */
export function getInterventionTypeLabel(type: string | null | undefined): string {
  if (!type) return "—";
  const lower = type.toLowerCase();
  return INTERVENTION_TYPE_LABELS[lower] || type;
}

/** Resolves a retention strategy code to its business label. */
export function getRetentionStrategyLabel(strategy: string | null | undefined): string {
  if (!strategy) return "—";
  const lower = strategy.toLowerCase();
  return RETENTION_STRATEGY_LABELS[lower] || strategy;
}

/** Resolves an ecosystem engagement level code to its business label. */
export function getEngagementLevelLabel(level: string | null | undefined): string {
  if (!level) return "—";
  const lower = level.toLowerCase();
  return ENGAGEMENT_LEVEL_LABELS[lower] || level;
}
