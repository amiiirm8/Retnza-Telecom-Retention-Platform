/**
 * Model Governance Page
 *
 * Comprehensive governance dashboard for the ML retention system. This page
 * surfaces all artifacts, contracts, and policies that comprise the ML
 * governance framework:
 *
 * ── Architecture: Governance Flow ──────────────────────────────────────────
 * Schema Compatibility (model, recommendations, SHAP)
 *   ↓ validates artifact alignment
 * Artifact Freshness
 *   ↓ ensures artifacts reflect current state
 * Threshold Policies (comparison table, positioning chart, impact analysis)
 *   ↓ evaluate recall/precision tradeoffs
 * Calibration Health (method selection, educational layer, method comparison)
 *   ↓ ensures reliable probability estimates
 * Executive Trust Panel
 *   ↓ 10 safeguards for production confidence
 * Technical Details (expandable raw JSON)
 *   ↓ full audit transparency
 *
 * Data contract: The backend `/model/governance` endpoint returns a
 * GovernanceResponse payload that this page renders into structured
 * executive views, preserving raw data in collapsible drawers.
 *
 * ── Data Flow ──────────────────────────────────────────────────────────────
 * 1. API call to `/model/governance` on mount
 * 2. Response parsed into typed interfaces (ThresholdPolicyEntry, etc.)
 * 3. Schema IDs resolved to business names via getSchemaInfo()
 * 4. Calibration candidates extracted from calibration_health.summary
 * 5. Freshness levels computed from artifact_freshness timestamps
 */

"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardTitle } from "@/components/ui/card";
import { CompatBadge } from "@/components/ui/badge";
import { PageLoading } from "@/components/ui/loading";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { JsonDrawer } from "@/components/ui/json-drawer";
import { TechnicalDrawer } from "@/components/ui/technical-drawer";
import { GovernanceSummaryBanner } from "@/components/governance/governance-summary-banner";
import { ThresholdPolicyCard } from "@/components/governance/threshold-policy-card";
import { PolicyComparisonTable } from "@/components/governance/policy-comparison-table";
import { CalibrationSummaryCard } from "@/components/governance/calibration-summary-card";
import { CalibrationMethodTable } from "@/components/governance/calibration-method-table";
import { ArtifactFreshnessList } from "@/components/governance/artifact-freshness-list";
import { PolicyBusinessImpactCard } from "@/components/governance/policy-business-impact-card";
import { PolicyPositioningChart } from "@/components/governance/policy-positioning-chart";
import { ConfusionMatrixExecutive } from "@/components/governance/confusion-matrix-executive";
import { CalibrationEducationalCard } from "@/components/governance/calibration-educational-card";
import { ExecutiveTrustPanel } from "@/components/governance/executive-trust-panel";
import { useI18n } from "@/i18n/provider";
import { getSchemaInfo, SCHEMA_DESCRIPTIONS } from "@/lib/governance-labels";
import { formatTimestamp } from "@/lib/governance-formatters";
import type { GovernanceResponse } from "@/types/api";

interface PolicyMetrics {
  precision: number;
  recall: number;
  f1: number;
  false_negative_rate: number;
  lift_at_threshold: number;
  base_rate: number;
}

interface ThresholdPolicyEntry {
  threshold: number;
  role: string;
  metrics: {
    validation?: PolicyMetrics;
    test?: PolicyMetrics;
  };
  calibration_curve?: Record<string, unknown>;
  confusion_matrix?: Record<string, unknown>;
}

interface CalibrationMethodDetail {
  method: string;
  validation_pr_auc: number | null;
  validation_brier: number | null;
  validation_ece: number | null;
  test_pr_auc: number | null;
  test_brier: number | null;
  test_ece: number | null;
  overfit_risk?: string;
}

export default function GovernancePage() {
  const { t, dir, locale } = useI18n();
  const [gov, setGov] = useState<GovernanceResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<GovernanceResponse>("/model/governance")
      .then(setGov)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <PageLoading />;
  if (!gov) return <p className="text-red-500">{t("common.error")}</p>;

  const policies: ThresholdPolicyEntry[] = gov.threshold_policies
    ? Object.entries(gov.threshold_policies)
        .map(([key, val]) => {
          if (typeof val !== "object" || val === null) return null;
          const entry = val as Record<string, unknown>;
          return {
            threshold: (entry.threshold as number) ?? 0,
            role: (entry.role as string) || key,
            metrics: entry.metrics as { validation?: PolicyMetrics; test?: PolicyMetrics } | undefined,
            calibration_curve: entry.calibration_curve,
            confusion_matrix: entry.confusion_matrix,
          } as ThresholdPolicyEntry;
        })
        .filter((p): p is ThresholdPolicyEntry => p !== null)
    : [];

  const recommendedRole = policies.find((p) => p.role === "primary_operating_policy")?.role;

  const calibrationMethods: CalibrationMethodDetail[] = gov.calibration_health?.summary
    ? (() => {
        const raw = gov.calibration_health.summary as Record<string, unknown>;
        const methods = raw.candidates || raw.methods || [];
        if (Array.isArray(methods)) return methods as CalibrationMethodDetail[];
        if (typeof methods === "object" && methods !== null) {
          return Object.values(methods) as CalibrationMethodDetail[];
        }
        return [];
      })()
    : [];

  const prAucCeiling = gov.calibration_health?.summary
    ? ((gov.calibration_health.summary as Record<string, unknown>).validation_pr_auc_ceiling as number | null)
    : null;

  const modelBundleInfo = getSchemaInfo(gov.schema_compatibility?.model?.bundle_schema_version);
  const modelingSchemaInfo = getSchemaInfo(gov.schema_compatibility?.model?.modeling_schema_version);
  const featureContractInfo = getSchemaInfo(gov.feature_contract_version);
  const recSchemaInfo = getSchemaInfo(gov.schema_compatibility?.recommendations?.schema_version);
  const shapSchemaInfo = getSchemaInfo(gov.schema_compatibility?.shap?.schema_version);

  return (
    <div className="space-y-6" dir={dir}>
      <header>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-900">{t("governance.title")}</h1>
          <CompatBadge status={gov.compatibility_status} />
        </div>
        <p className="mt-1 text-sm text-slate-500">{t("governance.description")}</p>
      </header>

      <GovernanceSummaryBanner gov={gov} />

      <ErrorBoundary section="Schema compatibility">
        <section>
          <h2 className="mb-4 text-lg font-bold text-slate-800">{t("governance.schemaCompatibility")}</h2>
        <div className="grid gap-6 lg:grid-cols-3">
          <Card>
            <div className="flex items-center justify-between">
              <CardTitle>{modelBundleInfo.friendlyName}</CardTitle>
              <CompatBadge status={gov.schema_compatibility?.model?.compatible ? "compatible" : "incompatible"} />
            </div>
            <p className="mt-1 text-xs text-slate-500 leading-relaxed">{SCHEMA_DESCRIPTIONS.model}</p>
            <SchemaRow label={t("governance.features")} value={gov.schema_compatibility?.model?.n_features} />
            <TechnicalDrawer
              title="Component Version Details"
              items={[
                { label: "Production Scoring Engine", value: modelBundleInfo.technicalId, mono: true },
                { label: "Model Specification", value: modelingSchemaInfo.technicalId, mono: true },
                { label: "Customer Signal Framework", value: featureContractInfo.technicalId, mono: true },
              ]}
              className="mt-3"
            />
            {gov.schema_compatibility?.model?.warnings?.length > 0 && (
              <div className="mt-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">
                {gov.schema_compatibility.model.warnings.map((w, i) => (
                  <p key={i}>{w}</p>
                ))}
              </div>
            )}
            {gov.schema_compatibility?.model?.errors?.length > 0 && (
              <div className="mt-2 rounded bg-red-50 px-2 py-1 text-xs text-red-700">
                {gov.schema_compatibility.model.errors.map((e, i) => (
                  <p key={i}>{e}</p>
                ))}
              </div>
            )}
          </Card>

          <Card>
            <div className="flex items-center justify-between">
              <CardTitle>{recSchemaInfo.friendlyName}</CardTitle>
              <CompatBadge status={gov.schema_compatibility?.recommendations?.compatible ? "compatible" : "incompatible"} />
            </div>
            <p className="mt-1 text-xs text-slate-500 leading-relaxed">{SCHEMA_DESCRIPTIONS.recommendations}</p>
            <SchemaRow label={t("governance.columns")} value={gov.schema_compatibility?.recommendations?.columns_present} />
            <TechnicalDrawer
              title="Component Version Details"
              items={[
                { label: "Retention Decision Engine", value: recSchemaInfo.technicalId, mono: true },
              ]}
              className="mt-3"
            />
            {gov.schema_compatibility?.recommendations?.warnings?.map((w, i) => (
              <p key={i} className="mt-2 text-xs text-amber-600">{w}</p>
            ))}
          </Card>

          <Card>
            <div className="flex items-center justify-between">
              <CardTitle>{shapSchemaInfo.friendlyName}</CardTitle>
              <CompatBadge status={gov.schema_compatibility?.shap?.compatible ? "compatible" : "incompatible"} />
            </div>
            <p className="mt-1 text-xs text-slate-500 leading-relaxed">{SCHEMA_DESCRIPTIONS.shap}</p>
            <TechnicalDrawer
              title="Component Version Details"
              items={[
                { label: "Customer Risk Driver Intelligence", value: shapSchemaInfo.technicalId, mono: true },
              ]}
              className="mt-3"
            />
            {gov.schema_compatibility?.shap?.warnings?.map((w, i) => (
              <p key={i} className="mt-2 text-xs text-amber-600">{w}</p>
            ))}
          </Card>
        </div>

        <div className="mt-4 rounded-lg border border-indigo-100 bg-indigo-50/50 px-4 py-3">
          <p className="text-xs font-medium text-indigo-700">{t("governance.whyThisMatters")}</p>
          <p className="mt-1 text-xs text-indigo-600 leading-relaxed">{SCHEMA_DESCRIPTIONS.whyThisMatters}</p>
        </div>
        </section>
      </ErrorBoundary>

      <ErrorBoundary section="Threshold policies">
        {policies.length > 0 && (
          <section>
            <h2 className="mb-4 text-lg font-bold text-slate-800">{t("governance.thresholds.title")}</h2>
          <p className="mb-4 text-xs text-slate-500">{t("governance.thresholds.explanation")}</p>
          <div className="space-y-4">
            <PolicyComparisonTable policies={policies} recommendedRole={recommendedRole} />
            <PolicyPositioningChart
              policies={policies.map((p) => ({
                role: p.role,
                threshold: p.threshold,
                metrics: p.metrics?.validation ?? null,
              }))}
              recommendedRole={recommendedRole}
            />
            <div className="grid gap-6 lg:grid-cols-2">
              {policies.map((p) => (
                <div key={p.role} className="space-y-4">
                  <ThresholdPolicyCard
                    policy={p}
                    isRecommended={p.role === recommendedRole}
                  />
                  <PolicyBusinessImpactCard
                    role={p.role}
                    metrics={p.metrics?.validation ?? null}
                  />
                  {p.confusion_matrix && (
                    <ConfusionMatrixExecutive
                      matrix={p.confusion_matrix}
                      metrics={p.metrics?.validation ?? null}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
      </ErrorBoundary>

      <ErrorBoundary section="Calibration health">
        <section>
          <h2 className="mb-4 text-lg font-bold text-slate-800">{t("governance.calibration.health")}</h2>
        <div className="space-y-4">
          <CalibrationSummaryCard
            selectedMethod={gov.calibration_health?.method || ""}
            prAucValidationCeiling={prAucCeiling}
            candidates={calibrationMethods}
            rawSummary={gov.calibration_health?.summary}
          />
          {calibrationMethods.length > 1 && (
            <CalibrationMethodTable methods={calibrationMethods} selectedMethod={gov.calibration_health?.method || ""} />
          )}
          {calibrationMethods.length > 0 && (
            <CalibrationEducationalCard
              selectedMethod={gov.calibration_health?.method || ""}
              candidates={calibrationMethods}
              validationPrAucCeiling={prAucCeiling}
            />
          )}
        </div>
      </section>
      </ErrorBoundary>

      <ErrorBoundary section="Artifact freshness">
        <ArtifactFreshnessList artifacts={gov.artifact_freshness} locale={locale} />
      </ErrorBoundary>

      {gov.production_notes && gov.production_notes.length > 0 && (
        <Card>
          <CardTitle>{t("governance.productionCautions")}</CardTitle>
          <ul className="mt-3 space-y-2">
            {gov.production_notes.map((note, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                <span className="text-slate-600">{note}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <ErrorBoundary section="Executive trust panel">
        <ExecutiveTrustPanel />
      </ErrorBoundary>

      <section>
        <h2 className="mb-4 text-lg font-bold text-slate-800">{t("governance.technical.title")}</h2>
        <div className="space-y-3">
          <JsonDrawer label={t("governance.technical.rawCompatibility")} data={gov.schema_compatibility} />
          <JsonDrawer label={t("governance.technical.rawPolicies")} data={gov.threshold_policies} />
          <JsonDrawer label={t("governance.technical.rawCalibration")} data={gov.calibration_health} />
          <JsonDrawer label={t("governance.technical.rawFreshness")} data={gov.artifact_freshness} />
        </div>
      </section>

      <div className="pt-4 text-center text-xs text-slate-400">
        {t("governance.lastChecked", {
          date: gov.schema_compatibility?.model?.checked_at_utc
            ? formatTimestamp(gov.schema_compatibility.model.checked_at_utc, locale)
            : "—",
        })}
      </div>
    </div>
  );
}

function SchemaRow({ label, value, mono }: { label: string; value: unknown; mono?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-500">{label}</span>
      <span className={mono ? "font-mono text-xs text-slate-700" : "font-medium text-slate-700"}>
        {value != null ? String(value) : "—"}
      </span>
    </div>
  );
}
