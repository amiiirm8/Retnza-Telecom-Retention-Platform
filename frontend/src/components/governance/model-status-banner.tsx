/**
 * Model Status Banner
 *
 * Health page banner summarizing model deployment status and production readiness.
 * Displays:
 * - Overall health status (compatible/warnings) with color-coded border
 * - Key performance metrics (PR-AUC, ECE, Brier)
 * - Model version tag and champion family
 * - Calibration method
 * - Operating threshold and active policy
 *
 * Health evaluation considers compatibility status AND metric health thresholds
 * (ECE < 0.05, PR-AUC > 0.3, Brier < 0.25) for a comprehensive assessment.
 */

import { useI18n } from "@/i18n/provider";
import { getPolicyRoleLabel } from "@/lib/governance-labels";

interface ModelStatusBannerProps {
  isCompatible: boolean;
  warningCount: number;
  prAuc: number | null;
  ece: number | null;
  brier: number | null;
  rocAuc: number | null;
  versionTag: string;
  championFamily: string;
  calibrationMethod: string | null;
  operatingThreshold: number | null;
  operatingPolicy: string | null;
}

export function ModelStatusBanner({
  isCompatible,
  warningCount,
  prAuc,
  ece,
  brier,
  versionTag,
  championFamily,
  calibrationMethod,
  operatingThreshold,
  operatingPolicy,
}: ModelStatusBannerProps) {
  const { t } = useI18n();

  const eceHealthy = ece != null && ece < 0.05;
  const prAucHealthy = prAuc != null && prAuc > 0.3;
  const brierHealthy = brier != null && brier < 0.25;

  const healthStatus = isCompatible && eceHealthy && prAucHealthy && brierHealthy
    ? t("health.exec.compatible")
    : t("health.exec.hasWarnings", { count: warningCount });

  const healthColor = isCompatible && eceHealthy && prAucHealthy && brierHealthy
    ? "border-l-emerald-500 text-emerald-700"
    : "border-l-amber-500 text-amber-700";

  const versionTagDisplay = versionTag || "—";
  const policyLabel = operatingPolicy ? getPolicyRoleLabel(operatingPolicy) : "—";

  return (
    <div className={`rounded-xl border border-slate-200 border-l-4 bg-gradient-to-br from-slate-50 to-white p-5 shadow-sm ${healthColor.replace("text-", "border-l-").split(" ")[0]}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-slate-400">{t("health.exec.healthStatus")}</p>
          <p className={`mt-1 text-lg font-semibold ${healthColor}`}>{healthStatus}</p>
          <p className="mt-1 text-xs text-slate-500">
            {t("health.exec.performanceSummary", {
              auc: prAuc?.toFixed(3) ?? "—",
              ece: ece?.toFixed(3) ?? "—",
              brier: brier?.toFixed(3) ?? "—",
            })}
          </p>
        </div>

        <div className="flex flex-wrap gap-4 text-xs">
          <div className="rounded-lg bg-slate-100 px-3 py-1.5">
            <p className="text-[10px] text-slate-400">{t("health.versionTag")}</p>
            <p className="mt-0.5 font-mono font-medium text-slate-700">{versionTagDisplay}</p>
          </div>
          <div className="rounded-lg bg-slate-100 px-3 py-1.5">
            <p className="text-[10px] text-slate-400">{t("health.championFamily")}</p>
            <p className="mt-0.5 font-medium text-slate-700">{championFamily}</p>
          </div>
          <div className="rounded-lg bg-slate-100 px-3 py-1.5">
            <p className="text-[10px] text-slate-400">{t("health.calibration")}</p>
            <p className="mt-0.5 font-medium text-slate-700">{calibrationMethod || "—"}</p>
          </div>
          {operatingThreshold != null && (
            <div className="rounded-lg bg-slate-100 px-3 py-1.5">
              <p className="text-[10px] text-slate-400">{t("health.operatingThreshold")}</p>
              <p className="mt-0.5 font-mono font-medium text-slate-700">{operatingThreshold.toFixed(4)}</p>
            </div>
          )}
          <div className="rounded-lg bg-slate-100 px-3 py-1.5">
            <p className="text-[10px] text-slate-400">{t("health.policy")}</p>
            <p className="mt-0.5 font-medium text-slate-700">{policyLabel}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
