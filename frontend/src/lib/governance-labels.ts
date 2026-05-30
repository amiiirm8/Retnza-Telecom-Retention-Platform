/**
 * Operational Governance Registry & Label Resolution
 *
 * ── Architecture Overview ─────────────────────────────────────────────────
 * This module serves as the single source of truth for operational component
 * metadata, policy labels, and governance descriptions across the entire
 * application. It formalizes the relationship between internal system
 * identifiers (from the backend ML pipeline) and their business-facing
 * enterprise semantics.
 *
 * ── Operational Intelligence Lifecycle ────────────────────────────────────
 * Scoring Flow:
 *   1. Customer Signal Framework defines 47 customer attributes engineered
 *      for churn prediction
 *   2. Operational Modeling Pipeline consumes the signal framework and
 *      produces raw churn probability scores
 *   3. Probability Reliability Layer transforms raw scores into trustworthy
 *      probability estimates for CRM decisioning
 *   4. Customer Risk Driver Intelligence generates per-customer driver
 *      explanations
 *   5. Retention Decision Engine applies business rules to produce
 *      retention actions
 *
 * ── Governance Flow ───────────────────────────────────────────────────────
 * System Alignment Status → Operational Intelligence Freshness
 * → Retention Intervention Policy Validation → Probability Reliability Health
 * → Production Readiness
 *
 * Every operational component registered here is validated for:
 * - System alignment (structural compatibility)
 * - Intelligence freshness (age since last update)
 * - Production availability (deployment integrity)
 *
 * ── Registries ────────────────────────────────────────────────────────────
 * - COMPONENT_REGISTRY: All production components, pipelines, and frameworks
 * - POLICY_ROLE_LABELS: Retention intervention policy naming
 * - CALIBRATION_METHOD_LABELS: Probability reliability technique catalog
 * - COMPATIBILITY_LABELS: Status labels for system alignment
 * - FRESHNESS_LABELS: Age-based intelligence health classification
 * - OPERATIONAL_LABELS: Operational component display names
 */

// ── Schema / Artifact Registry ─────────────────────────────────────────────

interface SchemaInfo {
  /** Business-friendly display name for dashboards and summaries */
  friendlyName: string;
  /** Operational description — what this artifact is and why it exists */
  description: string;
  /** Raw backend artifact identifier (preserved for audit traceability) */
  technicalId: string;
  /** Governance role description — how this artifact participates in governance */
  governanceRole: string;
  /** Operational purpose — why this artifact was created and how it is used */
  operationalPurpose: string;
}

/**
 * Schema ID alias table — maps legacy backend artifact identifiers to current
 * semantic keys. Preserved for backward compatibility so older backend payloads
 * continue to resolve without changing the contract.
 */
const LEGACY_SCHEMA_ALIASES: Record<string, string> = {
  "task4-v2": "feature-schema",
  "task7-shap-v4": "shap-explainability",
  "task8-recommendations-v4": "recommendation-engine",
  "modeling-v4": "intelligence-modeling",
  "champion-bundle-v4": "production-champion-bundle",
};

/**
 * Formal registry of all production operational components.
 *
 * Each entry documents:
 * - friendlyName: What reviewers see in dashboards and governance summaries
 * - description: What the component is and its domain purpose
 * - technicalId: The backend system identifier (preserved for lineage)
 * - governanceRole: How this component participates in governance validation
 * - operationalPurpose: Why this component exists and its system role
 *
 * Keys are semantic artifact identifiers. Legacy backend IDs (e.g. task4-v2)
 * are resolved via LEGACY_SCHEMA_ALIASES before lookup.
 */
const SCHEMA_REGISTRY: Record<string, SchemaInfo> = {
  "feature-schema": {
    friendlyName: "Customer Signal Framework",
    description:
      "Defines the 47 engineered telecom customer attributes — including usage patterns, tenure, spend behaviour, network generation, ecosystem adoption, and demographic profiles — used as input signals for churn prediction. This framework specifies signal names, types, value ranges, and transformation rules required by the production modeling pipeline.",
    technicalId: "feature-schema",
    governanceRole:
      "Input framework — validates signal alignment between model training and production scoring environments. Misalignment indicates a signal mismatch that would produce unreliable scores.",
    operationalPurpose:
      "Governs the structure, types, and validation rules for all customer signals consumed by the churn risk intelligence engine. Every scoring request is validated against this framework before inference.",
  },
  "intelligence-modeling": {
    friendlyName: "Operational Modeling Pipeline",
    description:
      "Production model training and scoring pipeline specification. Defines the signal engineering pipeline, model architecture hyperparameters, cross-validation strategy, and output score format for the churn prediction model family.",
    technicalId: "intelligence-modeling",
    governanceRole:
      "Pipeline framework — ensures consistency between training-time signal transformations and inference-time transformations to prevent silent data drift.",
    operationalPurpose:
      "Standardizes the modeling pipeline across development, validation, and production environments. All model candidates must comply with this specification.",
  },
  "production-champion-bundle": {
    friendlyName: "Churn Risk Intelligence Engine",
    description:
      "Complete production intelligence deployment containing the active model binary, probability reliability parameters, signal engineering configuration, and governance metadata. This deployment represents the current state of the production AI system.",
    technicalId: "production-champion-bundle",
    governanceRole:
      "Deployment framework — the intelligence engine must pass all alignment checks (customer signal framework, retention decision specification, risk driver specification) before it can serve production traffic.",
    operationalPurpose:
      "Packages the complete model intelligence set into a single deployable unit. Versioning ensures rollback capability and full production traceability.",
  },
  "shap-explainability": {
    friendlyName: "Customer Risk Driver Intelligence",
    description:
      "Defines the structure, validation rules, and metadata specification used for per-customer risk driver analysis. Governs the format for driver-level risk assessment including signal names, SHAP value ranges, narrative generation rules, and direction indicators (risk-increasing vs risk-reducing).",
    technicalId: "shap-explainability",
    governanceRole:
      "Risk driver framework — validates that risk driver output format is compatible with the current customer signal framework and retention decision specification. Misalignment means driver analysis cannot be reliably generated.",
    operationalPurpose:
      "Ensures all per-customer risk driver analysis is generated consistently and can be consumed by the subscriber detail view, executive dashboards, and retention play reasoning systems.",
  },
  "recommendation-engine": {
    friendlyName: "Retention Decision Engine",
    description:
      "Specification governing the production of retention actions, recommended plays, CRM routing metadata, and campaign assignment decisions. Defines the output structure for rule-based recommendation generation including action type, priority, channel assignment, and operational flags (escalation, human-touch, digital-only).",
    technicalId: "recommendation-engine",
    governanceRole:
      "Decision framework — validates that the recommendation engine outputs are structurally compatible with the CRM routing system and campaign analytics pipeline.",
    operationalPurpose:
      "Standardizes the recommendation engine output format so CRM teams, campaign systems, and operational dashboards can consume retention decisions consistently.",
  },
};

/** Resolves a backend artifact ID to its full SchemaInfo metadata. */
export function getSchemaInfo(id: string | null | undefined): SchemaInfo {
  if (!id) return { friendlyName: "—", description: "", technicalId: "", governanceRole: "", operationalPurpose: "" };
  const resolvedId = LEGACY_SCHEMA_ALIASES[id] || id;
  return (
    SCHEMA_REGISTRY[resolvedId] || {
      friendlyName: id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      description: "",
      technicalId: id,
      governanceRole: "",
      operationalPurpose: "",
    }
  );
}

/**
 * Architectural descriptions for each artifact category.
 * These explain the role each artifact plays in the overall ML system,
 * helping reviewers understand system boundaries and data flow.
 */
export const SCHEMA_DESCRIPTIONS = {
  model:
    "The production modeling pipeline currently in use. Defines the signal transformation, model architecture, and inference framework used for scoring all subscribers.",
  featureContract:
    "The engineered telecom customer signal framework consumed by the churn risk intelligence engine to predict churn risk. Every scoring request is validated against this framework.",
  recommendations:
    "The specification governing retention actions, plays, and recommended interventions. Ensures CRM systems receive structurally consistent decisions.",
  shap: "The specification governing per-customer risk driver analysis for driver-level intelligence. Validated against the customer signal framework to ensure driver names and values are consistent.",
  whyThisMatters:
    "All production components (model, recommendations, risk driver analysis) are aligned on the same customer signal framework and version specifications. This alignment ensures the system can safely score customers, generate actionable recommendations, and explain decisions without mismatch, data drift, or silent failures.",
};

// ── Threshold Policy Role Labels ────────────────────────────────────────────

/**
 * Business-facing labels for each retention intervention policy role.
 * These define the operational purpose of each policy in CRM retention workflows.
 */
const POLICY_ROLE_LABELS: Record<string, string> = {
  reference_baseline: "Reference Baseline for Strategy Comparison",
  primary_operating_policy: "Primary Operating Policy for Retention Actions",
  reference_only: "Secondary Benchmark Strategy",
  contact_budget_proxy: "CRM Capacity Planning Threshold",
};

function humanizeRole(role: string): string {
  return role.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Resolves a policy role ID to its business-facing label. Falls back to humanized role ID. */
export function getPolicyRoleLabel(role: string | null | undefined): string {
  if (!role) return "—";
  return POLICY_ROLE_LABELS[role] || humanizeRole(role);
}

/** Returns the intended operational use description for a retention intervention policy. */
export function getPolicyIntendedUse(role: string | null | undefined): string {
  if (!role) return "";
  const map: Record<string, string> = {
    reference_baseline: "Baseline threshold for strategy comparison and performance tracking across governance reviews.",
    primary_operating_policy: "Prioritizes recall to minimize missed churners in live retention operations.",
    reference_only: "Secondary benchmark for evaluating conservative vs aggressive retention approaches.",
    contact_budget_proxy: "Designed for CRM campaign capacity planning and outreach budget optimization.",
  };
  return map[role] || "";
}

/** Returns a business-facing interpretation of what the policy means for retention operations. */
export function getPolicyBusinessInterpretation(role: string | null | undefined): string {
  if (!role) return "";
  const map: Record<string, string> = {
    reference_baseline: "Maintained as a benchmarking reference rather than an actively deployed operational threshold. Enables comparison across governance review cycles.",
    primary_operating_policy: "Designed for retention operations where missed churners carry higher cost than false positives. Balances recall performance with operational workload.",
    reference_only: "Provides a conservative benchmark for governance review of whether the primary operating policy is correctly balanced for current conditions.",
    contact_budget_proxy: "Optimized for operational efficiency — balances CRM outreach capacity with expected retention lift for campaign planning.",
  };
  return map[role] || "";
}

/** Returns a detailed explanation of the policy's role, deployment status, and operational design rationale. */
export function getPolicyExplanation(role: string | null | undefined): string {
  if (!role) return "";
  const map: Record<string, string> = {
    reference_baseline: "This strategy is maintained as a benchmarking reference rather than an actively optimized operational threshold. It provides a consistent statistical baseline across governance review cycles.",
    primary_operating_policy: "The active policy for retention operations. Designed to minimize missed churners, accepting a higher false positive rate to ensure churners are identified for intervention.",
    reference_only: "This policy exists to compare conservative and aggressive retention approaches during governance reviews without affecting live operations.",
    contact_budget_proxy: "This threshold is designed for CRM workload planning rather than frontline deployment. It optimizes for operational capacity constraints.",
  };
  return map[role] || "";
}

// ── Calibration Method Labels & Rationale ───────────────────────────────────

const CALIBRATION_METHOD_LABELS: Record<string, string> = {
  isotonic: "Isotonic",
  sigmoid: "Sigmoid (Platt)",
  none: "None (Raw)",
};

/** Resolves a calibration method ID to its human-readable label. */
export function getCalibrationMethodLabel(method: string | null | undefined): string {
  if (!method) return "—";
  return CALIBRATION_METHOD_LABELS[method.toLowerCase()] || method;
}

/**
 * Returns a detailed explanation of why a calibration method was selected,
 * including tradeoffs, reliability implications for CRM, and monitoring recommendations.
 */
export function getCalibrationExplanation(method: string | null | undefined): string {
  if (!method) return "";
  const map: Record<string, string> = {
    isotonic:
      "Isotonic was selected because it stayed within the validation PR-AUC tolerance band while providing the strongest probability reliability for CRM decisioning, as reflected by calibration metrics such as Brier score and ECE. The tradeoff is a small ranking-performance change in exchange for better probability trustworthiness. Overfit risk is medium because the positive class sample is limited, so monitoring is recommended.",
    sigmoid:
      "Sigmoid (Platt scaling) assumes a parametric sigmoid shape for calibration. It is more robust with small samples but may not fit non-linear miscalibration patterns as well as isotonic.",
    none:
      "Raw model scores are used without calibration. This means probabilities may not be well-calibrated for CRM decision-making.",
  };
  return map[method.toLowerCase()] || "";
}

// ── CV Method Labels ─────────────────────────────────────────────────────────

const CV_METHOD_LABELS: Record<string, string> = {
  repeated_stratified_kfold: "Repeated Stratified Cross-Validation",
  stratified_kfold: "Stratified Cross-Validation",
  kfold: "Standard Cross-Validation",
  repeated_kfold: "Repeated Cross-Validation",
};

/** Resolves a backend CV method identifier to a readable label. Falls back to humanized raw value. */
export function getCvMethodLabel(method: string | null | undefined): string {
  if (!method) return "—";
  return CV_METHOD_LABELS[method.toLowerCase()] || method.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── Schema Compatibility Labels ─────────────────────────────────────────────

const COMPATIBILITY_LABELS: Record<string, string> = {
  compatible: "Compatible",
  incompatible: "Incompatible",
  unknown: "Unknown",
};

export function getCompatibilityLabel(status: string | null | undefined): string {
  if (!status) return "Unknown";
  return COMPATIBILITY_LABELS[status] || status;
}

// ── Artifact Freshness Classification ───────────────────────────────────────

export type FreshnessLevel = "fresh" | "recent" | "aging" | "stale";

/**
 * Evaluates an artifact's freshness based on its last update timestamp.
 * Classification tiers:
 * - fresh (< 24h): Recently updated, reflects current production state
 * - recent (< 7d): Within acceptable refresh window
 * - aging (< 30d): Should be refreshed soon
 * - stale (>= 30d): Review recommended — may reflect outdated state
 */
export function getFreshnessLevel(timestamp: string | null | undefined): {
  level: FreshnessLevel;
  label: string;
  hours: number;
} {
  if (!timestamp) return { level: "stale", label: "Unknown", hours: Infinity };
  const now = Date.now();
  const updated = new Date(timestamp).getTime();
  if (isNaN(updated)) return { level: "stale", label: "Unknown", hours: Infinity };
  const hours = (now - updated) / (1000 * 60 * 60);
  if (hours < 24) return { level: "fresh", label: "Fresh", hours };
  if (hours < 168) return { level: "recent", label: "Recent", hours };
  if (hours < 720) return { level: "aging", label: "Aging", hours };
  return { level: "stale", label: "Stale", hours };
}

/** Tailwind color classes for each freshness level. */
export const FRESHNESS_COLORS: Record<FreshnessLevel, string> = {
  fresh: "bg-emerald-50 text-emerald-700 border-emerald-200",
  recent: "bg-blue-50 text-blue-700 border-blue-200",
  aging: "bg-amber-50 text-amber-700 border-amber-200",
  stale: "bg-red-50 text-red-700 border-red-200",
};

/**
 * Human-readable labels for each freshness level.
 */
export const FRESHNESS_LABELS: Record<FreshnessLevel, string> = {
  fresh: "Fresh — updated within last 24 hours",
  recent: "Recent — updated within last 7 days",
  aging: "Aging — should be refreshed soon",
  stale: "Stale — review recommended, may reflect outdated state",
};

/**
 * Operational component display names.
 * These correspond to component type keys from the backend artifact_freshness
 * payload and represent the deployable intelligence components of the AI system.
 */
export const ARTIFACT_LABELS: Record<string, string> = {
  champion_model: "Churn Risk Intelligence Engine",
  recommendation_manifest: "Retention Decision Intelligence",
  shap_manifest: "Customer Risk Driver Intelligence",
  feature_manifest: "Customer Signal Framework",
  calibration_artifact: "Probability Reliability Layer",
};

/**
 * Legacy artifact labels mapped to current business terminology.
 * Preserved for backward compatibility: older backend payloads may reference
 * artifacts by their legacy keys (e.g. "task7-shap-v4") rather than the
 * current descriptive keys (e.g. "shap_manifest"). Keeping these aliases
 * prevents broken UI labels during the transition period.
 *
 * @deprecated These legacy keys exist only for backward compatibility with
 * older training-cycle artifacts. New payloads should use semantic keys.
 */
export const LEGACY_ARTIFACT_ALIASES: Record<string, string> = {
  champion_bundle_v4: "Churn Risk Intelligence Engine",
  "task7-shap-v4": "Customer Risk Driver Intelligence",
  "task8-recommendations-v4": "Retention Decision Engine",
  "task4-v2": "Customer Signal Framework",
  "modeling-v4": "Operational Modeling Pipeline",
};

// ── Missing-metric Reason Labels ───────────────────────────────────────────

/**
 * Returns an operational explanation for why metrics are absent for a
 * given retention intervention policy and dataset. Some policies intentionally
 * do not carry validation or test metrics by design (e.g., reference baselines).
 */
export function getMissingMetricReason(role: string | null | undefined): string {
  if (!role) return "This policy is maintained as a governance reference — performance metrics are not generated for standalone evaluation";
  const map: Record<string, string> = {
    reference_baseline: "This strategy is maintained as a benchmarking reference rather than an actively optimized operational threshold. Validation metrics reflect the baseline distribution only.",
    reference_only: "This policy exists to compare conservative and aggressive retention approaches during governance reviews. Standalone metrics are not applicable by design.",
  };
  // Default fallback for policies (e.g. contact_budget_proxy, primary_operating_policy) that
  // intentionally do not expose certain metrics — they are designed for planning or live deployment, not standalone evaluation
  return map[role] || `Operational metrics not generated for this policy — it serves a governance or planning role rather than frontline deployment`;
}
