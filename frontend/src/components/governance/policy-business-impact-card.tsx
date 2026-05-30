/**
 * Policy Business Impact Card
 *
 * Translates threshold policy metrics into actionable business impact estimates:
 * - Percentage of churners captured vs missed
 * - False alarm rate and estimated counts per 10K subscribers
 * - Policy aggressiveness classification
 * - Campaign workload and CRM staffing implications
 *
 * Each policy receives a recommendation badge (Production / Conservative /
 * Benchmark Only) and operational guidance for retention teams.
 */

import { useI18n } from "@/i18n/provider";
import { computeBusinessImpact, getPolicyRecommendationBadge, type PolicyMetrics } from "@/lib/governance-business-impact";

interface BusinessImpactCardProps {
  role: string;
  metrics: PolicyMetrics | null | undefined;
}

export function PolicyBusinessImpactCard({ role, metrics }: BusinessImpactCardProps) {
  const { t } = useI18n();
  const impact = computeBusinessImpact(metrics, role);
  const badge = getPolicyRecommendationBadge(role);

  if (!impact) return null;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${badge.color}`}>
          {badge.label}
        </span>
        <span className="text-[10px] text-slate-400 leading-relaxed">{badge.description}</span>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="rounded-lg bg-slate-50 px-2.5 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.businessImpact.captured")}</p>
          <p className="mt-0.5 text-sm font-semibold text-emerald-700">{impact.capturedChurnersPct.toFixed(1)}%</p>
          <p className="text-[9px] text-slate-400">~{impact.estimatedTruePositivesPer10k} per 10K subscribers</p>
        </div>

        <div className="rounded-lg bg-slate-50 px-2.5 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.businessImpact.missed")}</p>
          <p className="mt-0.5 text-sm font-semibold text-red-600">{impact.missedChurnersPct.toFixed(1)}%</p>
          <p className="text-[9px] text-slate-400">~{impact.estimatedMissedPer10k} per 10K subscribers</p>
        </div>

        <div className="rounded-lg bg-slate-50 px-2.5 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.businessImpact.falseAlarms")}</p>
          <p className="mt-0.5 text-sm font-semibold text-amber-600">{impact.falseAlarmsPct.toFixed(1)}%</p>
          <p className="text-[9px] text-slate-400">~{impact.estimatedFalseAlarmsPer10k} per 10K subscribers</p>
        </div>

        <div className="rounded-lg bg-slate-50 px-2.5 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.businessImpact.aggressiveness")}</p>
          <p className="mt-0.5 text-xs font-medium text-slate-700 leading-tight">{impact.aggressivenessLabel}</p>
        </div>

        <div className="rounded-lg bg-slate-50 px-2.5 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.businessImpact.workload")}</p>
          <p className="mt-0.5 text-xs font-medium text-slate-700 leading-tight">{impact.campaignWorkloadLabel}</p>
        </div>

        <div className="rounded-lg bg-slate-50 px-2.5 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.businessImpact.staffing")}</p>
          <p className="mt-0.5 text-[10px] text-slate-600 leading-relaxed">{impact.crmStaffingImplication}</p>
        </div>
      </div>
    </div>
  );
}
