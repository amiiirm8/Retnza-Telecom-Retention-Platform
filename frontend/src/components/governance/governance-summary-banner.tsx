/**
 * Governance Summary Banner
 *
 * Top-level executive summary of model governance health. Displays:
 * - Schema compatibility status (compatible/incompatible)
 * - Calibration method and health
 * - Model schema and feature contract versions
 * - SHAP explainability compatibility
 * - Artifact freshness levels with staleness warnings
 *
 * This is the primary governance entry point for executives reviewing
 * system health and deployment readiness.
 */

import { useI18n } from "@/i18n/provider";
import { CompatBadge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { getCalibrationMethodLabel, getFreshnessLevel, FRESHNESS_COLORS, getSchemaInfo, getPolicyRoleLabel } from "@/lib/governance-labels";
import { formatFreshnessDescription } from "@/lib/governance-formatters";
import type { GovernanceResponse } from "@/types/api";

interface GovernanceSummaryBannerProps {
  gov: GovernanceResponse;
}

export function GovernanceSummaryBanner({ gov }: GovernanceSummaryBannerProps) {
  const { t } = useI18n();
  const isCompatible = gov.compatibility_status === "compatible";
  const modelBundleInfo = getSchemaInfo(gov.schema_compatibility?.model?.bundle_schema_version);
  const featureContractInfo = getSchemaInfo(gov.feature_contract_version);

  const freshnessLevels = Object.entries(gov.artifact_freshness || {}).map(([key, ts]) => ({
    key,
    ts,
    level: getFreshnessLevel(ts),
  }));

  const allFresh = freshnessLevels.every((f) => f.level.level === "fresh" || f.level.level === "recent");

  const recSchemaInfo = getSchemaInfo(gov.schema_compatibility?.recommendations?.schema_version);
  const shapSchemaInfo = getSchemaInfo(gov.schema_compatibility?.shap?.schema_version);

  return (
    <Card className={`border-l-4 ${isCompatible ? "border-l-emerald-500" : "border-l-red-500"} bg-gradient-to-br from-slate-50 to-white`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-base font-bold text-slate-800">{t("governance.summary.title")}</h2>
            <CompatBadge status={gov.compatibility_status} />
          </div>
          <p className={`mt-1 text-sm font-medium ${isCompatible ? "text-emerald-700" : "text-red-700"}`}>
            {isCompatible ? t("governance.summary.healthy") : t("governance.summary.issuesDetected")}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {gov.calibration_health?.method && (
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.summary.calibration")}</p>
            <p className="mt-0.5 text-sm font-semibold text-slate-800">{getCalibrationMethodLabel(gov.calibration_health.method)}</p>
          </div>
        )}
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.summary.modelSchema")}</p>
          <p className="mt-0.5 text-sm font-semibold text-slate-800">{modelBundleInfo.friendlyName}</p>
          {modelBundleInfo.technicalId && (
            <p className="text-[10px] font-mono text-slate-400">Technical ID: {modelBundleInfo.technicalId}</p>
          )}
          {modelBundleInfo.governanceRole && (
            <p className="mt-0.5 text-[9px] text-slate-400 leading-relaxed">{modelBundleInfo.governanceRole}</p>
          )}
        </div>
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.summary.featureContract")}</p>
          <p className="mt-0.5 text-sm font-semibold text-slate-800">{featureContractInfo.friendlyName}</p>
          {featureContractInfo.technicalId && (
            <p className="text-[10px] font-mono text-slate-400">Technical ID: {featureContractInfo.technicalId}</p>
          )}
          {featureContractInfo.governanceRole && (
            <p className="mt-0.5 text-[9px] text-slate-400 leading-relaxed">{featureContractInfo.governanceRole}</p>
          )}
        </div>
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.summary.explainability")}</p>
          <p className="mt-0.5 text-sm font-semibold text-slate-800">
            <CompatBadge status={gov.schema_compatibility?.shap?.compatible ? "compatible" : "incompatible"} />
          </p>
          {shapSchemaInfo.governanceRole && (
            <p className="mt-0.5 text-[9px] text-slate-400 leading-relaxed">{shapSchemaInfo.governanceRole}</p>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
        <p>{featureContractInfo.description}</p>
      </div>

      <div className="mt-2 flex flex-wrap gap-4 text-[10px] text-slate-400">
        {modelBundleInfo.operationalPurpose && (
          <p className="max-w-md leading-relaxed">
            <span className="font-medium">Model role:</span> {modelBundleInfo.operationalPurpose}
          </p>
        )}
        {recSchemaInfo.governanceRole && (
          <p className="max-w-md leading-relaxed">
            <span className="font-medium">Recommendations:</span> {recSchemaInfo.governanceRole}
          </p>
        )}
      </div>

      {gov.threshold_policies && (
        <div className="mt-2 text-xs text-slate-500">
          {t("governance.summary.policy")}: {getPolicyRoleLabel(
            Object.keys(gov.threshold_policies).find((k) => {
              const v = (gov.threshold_policies as Record<string, unknown>)[k] as Record<string, unknown>;
              return v?.role === "primary_operating_policy";
            })
          )}
        </div>
      )}

      {freshnessLevels.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-medium text-slate-400">{t("governance.summary.artifactFreshness")}:</span>
          {freshnessLevels.map((f) => {
            const color = FRESHNESS_COLORS[f.level.level];
            return (
              <span
                key={f.key}
                className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${color}`}
                title={formatFreshnessDescription(f.ts)}
              >
                {f.level.label}
              </span>
            );
          })}
        </div>
      )}

      {!allFresh && (
        <p className="mt-2 text-xs text-amber-600">{t("governance.summary.staleArtifactWarning")}</p>
      )}
    </Card>
  );
}
