/**
 * Retention Recommendation Narrative Builder
 *
 * Assembles a comprehensive narrative for each retention recommendation
 * by combining data from the catalog, rule labels, and action resolution.
 *
 * The narrative serves as the single source of truth for displaying
 * retention decisions throughout the application — in subscriber profiles,
 * queue views, campaign summaries, and executive dashboards.
 *
 * Architecture notes:
 * - The catalog provides structured playbook entries (business name, target,
 *   urgency, channels, offers, guidance)
 * - Rule labels supply the human-readable rule description
 * - Action resolution converts the recommended action code to full text
 * - The narrative also includes urgency/intervention/complexity labels
 *   with operational timeframes
 *
 * SHAP does NOT influence the narrative content — it provides driver analysis
 * separately in the subscriber detail view. The narrative is purely rule-driven.
 */

import { getCatalogEntry } from "./recommendation-catalog";
import { getExecutiveRuleName, getRuleDescription } from "./rule-labels";
import { getFullActionText } from "./label-resolver";

/**
 * Complete narrative payload for a single retention recommendation.
 * Constructed by merging catalog data, rule labels, and resolved action text.
 * Serves as the single display contract for all UI surfaces.
 */
export interface RecommendationNarrative {
  /** Executive-facing play name (e.g. "Bill Shock Vulnerability") */
  businessName: string;
  /** One-paragraph summary of why this recommendation applies */
  executiveSummary: string;
  /** Human-readable trigger condition from the rule label registry */
  ruleDescription: string;
  /** Subscriber segment the recommendation targets */
  targetSegment: string;
  /** Business objective this play aims to achieve */
  retentionObjective: string;
  /** Ordered list of contact channels (primary first) */
  suggestedChannels: string[];
  /** Human-readable urgency with operational timeframe (e.g. "Immediate — act within 24 hours") */
  urgencyLabel: string;
  /** Human-readable intervention type with execution model (e.g. "Digital outreach — automated") */
  interventionLabel: string;
  /** Catalog-defined playbook offers the CRM team can execute */
  playbookOffers: { title: string; description: string; channel: string }[];
  /** CRM team instructions for executing this play */
  operationalGuidance: string;
  /** Measurable outcome that defines this play as successful */
  successSignal: string;
  /** Human-readable complexity estimate (e.g. "Low — standard playbook") */
  estimatedComplexityLabel: string;
  /** Resolved action text (e.g. "Offer retention incentive — discount or bonus") */
  fullActionText: string;
  /** Backend rule identifier preserved for traceability (e.g. "R05_BILL_SHOCK") */
  technicalRuleId: string;
}

/**
 * Time-to-act labels keyed by catalog urgency codes.
 * These operational windows guide CRM teams on prioritization:
 *   24h for critical churn signals, 7d for standard outreach, 30d for planned campaigns.
 */
const URGENCY_LABELS: Record<string, string> = {
  immediate: "Immediate — act within 24 hours",
  "short-term": "Short-term — act within 7 days",
  planned: "Planned — schedule within 30 days",
};

/**
 * Channel type labels explaining the execution model behind each intervention.
 * "hybrid" begins with digital and escalates to a human agent if no response,
 * reducing cost while preserving human-touch for high-value cases.
 */
const INTERVENTION_LABELS: Record<string, string> = {
  digital: "Digital outreach — automated",
  "human-touch": "Human-touch — agent required",
  hybrid: "Hybrid — digital first, escalate to agent",
};

/**
 * Complexity labels mapping catalog complexity to CRM resource estimates.
 * "low" = fully automated playbook; "high" = multi-step coordination (e.g. call + device subsidy + ecosystem activation).
 */
const COMPLEXITY_LABELS: Record<string, string> = {
  low: "Low — standard playbook",
  medium: "Medium — requires some configuration",
  high: "High — multi-step coordination needed",
};

/**
 * Builds a complete recommendation narrative for display across the application.
 *
 * @param ruleId - The retention rule ID (R00–R13) that was triggered
 * @param action - The recommended action code from the recommendation engine
 * @returns A fully populated RecommendationNarrative with catalog data where available,
 *          or a minimal fallback narrative for unknown/uncataloged rules
 */
export function buildRecommendationNarrative(
  ruleId: string | null | undefined,
  action: string | null | undefined,
): RecommendationNarrative {
  const rid = ruleId ?? null;
  const act = action ?? null;
  const catalog = getCatalogEntry(rid);
  const businessName = getExecutiveRuleName(rid);
  const fullActionText = getFullActionText(act);
  const ruleDescription = getRuleDescription(rid);

  if (!catalog) {
    return {
      businessName,
      executiveSummary: ruleDescription || "Recommendation based on model output.",
      ruleDescription,
      targetSegment: "General subscriber base",
      retentionObjective: fullActionText,
      suggestedChannels: [],
      urgencyLabel: "Standard",
      interventionLabel: "Standard",
      playbookOffers: [],
      operationalGuidance: "Refer to CRM queue for details.",
      successSignal: "Monitor churn probability change in next scoring cycle.",
      estimatedComplexityLabel: "Unknown",
      fullActionText,
      technicalRuleId: rid || "—",
    };
  }

  return {
    businessName: catalog.businessName,
    executiveSummary: catalog.executiveSummary,
    ruleDescription,
    targetSegment: catalog.targetSegment,
    retentionObjective: catalog.retentionObjective,
    suggestedChannels: catalog.suggestedChannels,
    urgencyLabel: URGENCY_LABELS[catalog.urgency] || catalog.urgency,
    interventionLabel: INTERVENTION_LABELS[catalog.interventionType] || catalog.interventionType,
    playbookOffers: catalog.playbookOffers,
    operationalGuidance: catalog.operationalGuidance,
    successSignal: catalog.successSignal,
    estimatedComplexityLabel:
      COMPLEXITY_LABELS[catalog.estimatedComplexity] || catalog.estimatedComplexity,
    fullActionText,
    technicalRuleId: catalog.id,
  };
}

/**
 * Builds a condensed one-line playbook summary for list views and tooltips.
 * Combines the retention objective, target segment, and suggested channels.
 * Returns empty string for unknown/unregistered rule IDs.
 */
export function buildPlaybookSummary(ruleId: string | null): string {
  const catalog = getCatalogEntry(ruleId);
  if (!catalog) return "";
  return `${catalog.retentionObjective} — ${catalog.targetSegment}. ${catalog.suggestedChannels.join(", ")}.`;
}
