import type { ReactNode } from "react";

// ── Auth ──────────────────────────────────────────────────────────────────

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserOut {
  id: number;
  email: string;
  is_active: boolean;
  role: string;
}

// ── Recommendation Item ────────────────────────────────────────────────────

/**
 * A single retention recommendation row returned by the backend scoring pipeline.
 * Contains the churn prediction, assigned risk tier, triggered rule, recommended
 * action, and CRM routing metadata (queue, channel, priority, intervention type).
 * Each row represents one subscriber that the ML + rule engine has evaluated.
 */
export interface RecommendationItem {
  subscriber_id: number;
  churn_probability: number | null;
  churn_probability_raw: number | null;
  risk_tier: string | null;
  rule_id: string | null;
  recommended_action: string | null;
  campaign_priority: string | null;
  campaign_cost_tier: string | null;
  campaign_queue_rank: number | null;
  crm_queue: string | null;
  digital_only_flag: boolean | null;
  escalation_required: boolean | null;
  human_touch_flag: boolean | null;
  primary_channel: string | null;
  secondary_channel: string | null;
  campaign_channel_group: string | null;
  intervention_type: string | null;
  ecosystem_segment: string | null;
  ecosystem_retention_strategy: string | null;
  rule_top_driver: string | null;
  shap_top_driver: string | null;
  final_top_driver: string | null;
  final_top_driver_source: string | null;
  top_driver: string | null;
}

export interface RecommendationListResponse {
  total: number;
  page: number;
  page_size: number;
  items: RecommendationItem[];
}

export interface ActionQueueResponse extends RecommendationListResponse {
  queue_type: string;
  filters: Record<string, unknown>;
}

// ── Subscriber Profile ─────────────────────────────────────────────────────

/**
 * Core subscriber attributes used as input features for churn prediction.
 * These fields feed directly into the model's feature engineering pipeline.
 */
export interface SubscriberProfileBase {
  age: number | null;
  gender: string | null;
  sim_card_type: string | null;
  sim_tenure_months: number | null;
  mobile_data_generation: string | null;
  monthly_spend_toman: number | null;
  churn_actual: boolean | null;
}

export interface SubscriberScore {
  churn_probability: number | null;
  churn_probability_raw: number | null;
  risk_tier: string | null;
  calibration_method: string | null;
}

/**
 * A single SHAP driver contributing to a subscriber's churn prediction.
 * Each driver has a field name, its SHAP value (magnitude of impact),
 * a human-readable narrative, and a direction indicator
 * ("increases_risk" or "decreases_risk").
 */
export interface ShapDriver {
  /** Feature/field name from the signal framework */
  field: string;
  /** Human-readable label for display in driver explanations */
  business_label: string;
  /** SHAP value — magnitude and sign of the feature's contribution to the prediction */
  shap_value: number;
  /** Generated explanation text describing why this driver matters */
  narrative: string;
  /** "increases_risk" or "decreases_risk" — directly maps to positive_drivers / negative_drivers grouping */
  direction: string;
}

/**
 * Per-subscriber SHAP explanation payload.
 * Drivers are pre-split into positive (risk-increasing) and negative
 * (risk-reducing) groups by the backend for simpler frontend rendering.
 */
export interface SubscriberShapExplanation {
  /** Drivers that increase churn risk (positive SHAP values) */
  positive_drivers: ShapDriver[];
  /** Drivers that decrease churn risk (negative SHAP values) */
  negative_drivers: ShapDriver[];
  /** Free-text narrative summarizing the overall SHAP explanation */
  narrative: string | null;
  /** The single strongest risk-increasing driver name */
  shap_top_driver: string | null;
  /** Comma-separated list of risk-increasing driver names (for tooltips / badges) */
  shap_risk_up_drivers: string | null;
  /** Comma-separated list of risk-reducing driver names (for tooltips / badges) */
  shap_risk_down_drivers: string | null;
}

export interface SubscriberEcosystemProfile {
  has_rubika: boolean | null;
  has_ewano: boolean | null;
  has_hamrahman: boolean | null;
  has_volte: boolean | null;
  ecosystem_product_count: number | null;
  ecosystem_engagement_level: string | null;
  ecosystem_segment: string | null;
  ecosystem_risk_gap: number | null;
  ecosystem_retention_strategy: string | null;
}

export interface CampaignMetadata {
  campaign_priority: string | null;
  campaign_cost_tier: string | null;
  crm_queue: string | null;
  primary_channel: string | null;
  secondary_channel: string | null;
  campaign_channel_group: string | null;
  digital_only_flag: boolean | null;
  escalation_required: boolean | null;
  human_touch_flag: boolean | null;
  campaign_urgency_days: number | null;
  contact_channel: string | null;
  offer_budget: number | null;
}

export interface GovernanceMetadata {
  schema_version: string | null;
  bundle_schema_version: string | null;
  feature_contract_version: string | null;
  recommendation_schema_version: string | null;
  shap_schema_version: string | null;
  compatibility_status: string | null;
  champion_family: string | null;
}

// ── EDA / Evidence ─────────────────────────────────────────────────────────

export interface EDAChurnRow {
  sim_card_type?: string;
  tenure_band?: string;
  mobile_data_generation?: string;
  volte_service?: string;
  n: number;
  churn_rate: number;
  lift: number;
}

export interface EDANarrative {
  key: string;
  bullets: string[];
}

export interface EDAResponse {
  n_subscribers: number;
  mean_calibrated_risk: number;
  churn_by_sim: EDAChurnRow[];
  churn_by_tenure: EDAChurnRow[];
  churn_by_generation: EDAChurnRow[];
  churn_by_sim_and_generation: EDAChurnRow[];
  volte_impact: EDAChurnRow[];
  executive_narratives: EDANarrative[];
  retention_simulation: Record<string, unknown>;
  top_shap_features: string[];
  generated_at_utc: string;
}

/**
 * Complete subscriber profile assembled by the backend from multiple
 * pipeline outputs: core attributes, ML score, recommendation, ecosystem,
 * SHAP explanations, campaign metadata, and governance metadata.
 * This is the top-level contract for the subscriber detail API endpoint.
 */
export interface SubscriberProfile {
  subscriber_id: number;
  profile: SubscriberProfileBase;
  score: SubscriberScore;
  risk_band: string | null;
  recommendation: RecommendationItem | null;
  ecosystem_profile: SubscriberEcosystemProfile;
  shap_explanations: SubscriberShapExplanation;
  recommendation_rationale: {
    rule_id: string | null;
    rule_top_driver: string | null;
    final_top_driver: string | null;
    final_top_driver_source: string | null;
    policy: string;
  };
  campaign_metadata: CampaignMetadata;
  governance_metadata: GovernanceMetadata;
}

// ── Dashboard ──────────────────────────────────────────────────────────────

export interface KPIResponse {
  total_subscribers: number;
  actual_churn_rate: number;
  avg_predicted_churn: number;
  high_risk_count: number;
  p1_action_count: number;
  executive_summary: string;
}

export interface ChartsResponse {
  risk_distribution: { name: string; value: number }[];
  rule_distribution: { name: string; value: number }[];
  campaign_priority_distribution: { name: string; value: number }[];
}

// ── Ecosystem ──────────────────────────────────────────────────────────────

export interface AdoptionMetric {
  label: string;
  active_n: number;
  inactive_capable_n: number;
  adoption_rate: number;
  mean_calibrated_risk_active: number;
  mean_calibrated_risk_inactive_capable: number;
  observed_relationship: string;
}

export interface EcosystemSummary {
  disclaimer: string;
  book_mean_calibrated_risk: number;
  rubika_adoption: AdoptionMetric;
  ewano_adoption: AdoptionMetric;
  hamrah_man_engagement: AdoptionMetric;
  volte_usage: AdoptionMetric;
  ecosystem_segment_counts: Record<string, number>;
  manifest_analytics: Record<string, unknown>;
}

export interface SegmentInfo {
  ecosystem_segment: string;
  n: number;
  mean_calibrated_risk: number | null;
  wording: string;
}

export interface EcosystemSegments {
  segments: SegmentInfo[];
  segment_taxonomy: string[];
  disclaimer: string;
}

// ── Model Health ───────────────────────────────────────────────────────────

/**
 * A single operating threshold configuration for the retention decision engine.
 * Defines the cutoff probability and associated policy name (e.g. "primary_operating_policy")
 * along with tier-specific thresholds that map probability ranges to risk tiers.
 */
export interface ThresholdPolicy {
  operating_threshold: number;
  operating_policy: string;
  risk_tier_thresholds: Record<string, number>;
}

/**
 * Model health and governance status from the monitoring API.
 * Aggregates performance metrics (PR-AUC, ROC-AUC, Brier, ECE),
 * version tags, calibration method, schema compatibility status,
 * artifact freshness timestamps, and active warning flags.
 */
export interface ModelHealth {
  pr_auc: number | null;
  roc_auc: number | null;
  brier: number | null;
  ece: number | null;
  version_tag: string;
  champion_family: string;
  calibration_method: string;
  schema_version: string;
  bundle_schema_version: string;
  feature_contract_version: string;
  recommendation_schema_version: string;
  compatibility_status: string;
  threshold_policy: ThresholdPolicy;
  artifact_freshness: Record<string, string>;
  warnings: string[];
}

export interface DriftResponse {
  schema_version: string;
  model_family: string;
  calibration_method: string;
  n_features: number;
  drift_summary: Record<string, unknown>;
  psi_references: Record<string, unknown>;
  score_histograms: Record<string, unknown>;
  baseline_metrics_holdout: Record<string, unknown>;
  monitoring_notes: string[];
  artifact_freshness: Record<string, string>;
}

export interface CvStats {
  pr_auc_mean: number | null;
  pr_auc_std: number | null;
  roc_auc_mean: number | null;
  roc_auc_std: number | null;
  brier_mean: number | null;
  brier_std: number | null;
}

export interface StabilityResponse {
  generated_at_utc: string;
  method: string;
  cv_mean_std: Record<string, CvStats>;
  family_comparison: unknown[];
  selection_rationale: Record<string, unknown>;
  champion_family: string;
  schema_version: string;
}

export interface SchemaCompatibility {
  compatible: boolean;
  warnings: string[];
  errors: string[];
  checked_at_utc: string;
}

export interface ModelSchemaCompatibility extends SchemaCompatibility {
  n_features: number;
  bundle_schema_version: string;
  modeling_schema_version: string;
}

export interface RecommendationsSchemaCompatibility extends SchemaCompatibility {
  schema_version: string;
  columns_present: number;
}

export interface ShapSchemaCompatibility extends SchemaCompatibility {
  schema_version: string;
}

export interface CalibrationHealth {
  method: string;
  summary: Record<string, unknown> | null;
}

/**
 * Top-level governance validation response from the backend.
 * Contains schema compatibility checks for all operational components
 * (model, recommendations, SHAP), artifact freshness, threshold policies,
 * calibration health, and production notes. Used by the governance dashboard
 * to display system alignment status.
 */
export interface GovernanceResponse {
  schema_compatibility: {
    model: ModelSchemaCompatibility;
    recommendations: RecommendationsSchemaCompatibility;
    shap: ShapSchemaCompatibility;
  };
  feature_contract_version: string;
  artifact_validation: Record<string, unknown>;
  shap_compatibility: Record<string, unknown> | null;
  recommendation_compatibility: Record<string, unknown> | null;
  compatibility_status: string;
  artifact_freshness: Record<string, string>;
  threshold_policies: Record<string, unknown>;
  calibration_health: CalibrationHealth;
  production_notes: string[];
}

// ── Predict ────────────────────────────────────────────────────────────────

/**
 * Single-subscriber prediction response from the real-time inference endpoint.
 * Returns the rule ID, risk tier, churn probabilities (calibrated and raw),
 * top driver attribution, recommended action, and SHAP narrative.
 * Used by the single-subscriber lookup feature.
 */
export interface PredictResponse {
  rule_id: string;
  risk_tier: string;
  churn_probability: number;
  churn_probability_raw: number;
  final_top_driver: string;
  final_top_driver_source: string;
  top_driver: string;
  recommended_action: string;
  shap_narrative: string;
}

// ── Utility ────────────────────────────────────────────────────────────────

export interface PageProps {
  params: Promise<Record<string, string>>;
}

export interface LayoutProps {
  children: ReactNode;
}
