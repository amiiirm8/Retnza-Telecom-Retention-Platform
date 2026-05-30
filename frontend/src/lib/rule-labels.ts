/**
 * Retention Rule Label Registry
 *
 * Maps internal retention rule IDs (R00–R13) to business-readable names
 * and descriptions. These rules represent the deterministic decision logic
 * that maps subscriber characteristics to recommended retention actions.
 *
 * The rule engine is explicit and auditable — recommendations are driven
 * by business rules, not by the ML model directly. SHAP explainability
 * provides narrative context only; it does not determine the action.
 *
 * Each rule has:
 * - businessName: Executive-facing name for dashboards and summaries
 * - description: Plain-English explanation of the rule trigger condition
 *
 * The registry supports forward-compatible fallback: unknown rule IDs
 * display as "Retention Play" with a development-mode console warning
 * to encourage catalog updates.
 */

/** Executive-facing names for each retention rule. */
export const RULE_EXEC_LABELS: Record<string, string> = {
  R00_MONITOR: "Monitor Emerging Risk",
  R01_PREPAID_INFANT: "New Prepaid User Risk",
  R02_PREPAID_5G: "5G Prepaid Churn Exposure",
  R03_POSTPAID_INFANT: "New Postpaid User Risk",
  R03_VOLTE_ENABLE: "VoLTE Migration Opportunity",
  R04_POSTPAID_5G: "5G Postpaid Churn Exposure",
  R05_BILL_SHOCK: "Bill Shock Vulnerability",
  R06_VOLTE_INACTIVE: "VoLTE Non-Adoption",
  R06_VAS_PARTIAL: "Low Service Engagement",
  R07_LEGACY_2G: "Legacy Network Dependency",
  R08_LEGACY_3G: "Legacy Network Dependency",
  R08_POSTPAID_EARLY: "Early Lifecycle Postpaid Risk",
  R09_RUBIKA_INACTIVE: "Low Rubika Engagement",
  R10_EWANO_NON_ADOPTER: "EWANO Non-Adoption",
  R11_HAMRAHMAN_LOW_ENGAGEMENT: "Low Hamrah Man Engagement",
  R12_ECOSYSTEM_POWER_USER: "High Loyalty Ecosystem Users",
  R13_LEGACY_2G_ECO_DISENGAGED: "Legacy User — Ecosystem Disengaged",
};

/** Plain-English descriptions of the trigger condition for each retention rule. */
export const RULE_DESCRIPTIONS: Record<string, string> = {
  R00_MONITOR:
    "Customers showing mild early churn indicators requiring observation and low-touch engagement",
  R01_PREPAID_INFANT:
    "New prepaid subscribers with limited tenure history",
  R02_PREPAID_5G:
    "Prepaid 5G users showing early churn signals",
  R03_POSTPAID_INFANT:
    "New postpaid subscribers in the early tenure window",
  R03_VOLTE_ENABLE:
    "VoLTE-capable subscribers who are not actively using VoLTE services",
  R04_POSTPAID_5G:
    "Postpaid 5G users with elevated churn probability",
  R05_BILL_SHOCK:
    "Subscribers with sudden bill increases above threshold",
  R06_VOLTE_INACTIVE:
    "VoLTE-capable subscribers who have not adopted",
  R06_VAS_PARTIAL:
    "Subscribers with limited adoption of digital or value-added services",
  R07_LEGACY_2G:
    "Subscribers still on 2G network with limited data usage",
  R08_LEGACY_3G:
    "Subscribers still on 3G network with limited data usage",
  R08_POSTPAID_EARLY:
    "Recently onboarded postpaid subscribers with elevated early-tenure churn sensitivity",
  R09_RUBIKA_INACTIVE:
    "Rubika-capable users who are inactive on the platform",
  R10_EWANO_NON_ADOPTER:
    "EWANO-capable subscribers who have not activated",
  R11_HAMRAHMAN_LOW_ENGAGEMENT:
    "Hamrah Man users with below-threshold engagement",
  R12_ECOSYSTEM_POWER_USER:
    "Multi-product ecosystem users with high loyalty scores",
  R13_LEGACY_2G_ECO_DISENGAGED:
    "2G legacy users not engaged with any ecosystem product",
};

/**
 * Resolves a rule ID to its executive-facing display name.
 * Returns "Retention Play" for unknown IDs (with dev warning in development mode).
 */
export function getExecutiveRuleName(ruleId: string | null | undefined): string {
  if (!ruleId) return "—";
  if (RULE_EXEC_LABELS[ruleId]) return RULE_EXEC_LABELS[ruleId];
  if (typeof ruleId === "string" && ruleId.startsWith("R")) {
    // Forward-compatible fallback: if the backend introduces a new rule ID (R14+)
    // before the label registry is updated, display a generic name instead of
    // showing the raw code. The dev-mode warning alerts developers to add the label.
    if (process.env.NODE_ENV === "development") {
      console.warn(
        `[rule-labels] Missing executive label for "${ruleId}" — add to RULE_EXEC_LABELS`,
      );
    }
    return "Retention Play";
  }
  const humanized = ruleId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return humanized || "—";
}

/**
 * Resolves a rule ID to its trigger condition description.
 * Returns empty string for unknown IDs.
 */
export function getRuleDescription(ruleId: string | null | undefined): string {
  if (!ruleId) return "";
  return RULE_DESCRIPTIONS[ruleId] || "";
}
