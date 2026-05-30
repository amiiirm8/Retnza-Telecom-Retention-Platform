/**
 * Stability Explainability Card
 *
 * Cross-validation stability analysis showing how consistently the model
 * performs across training folds. Uses standard deviation of PR-AUC across
 * folds as the stability metric:
 *
 * - σ < 0.02: Stable — high confidence in generalization
 * - σ 0.02–0.05: Monitor — moderate variance
 * - σ >= 0.05: Unstable — model may not generalize well
 *
 * Displays an overall stability status banner, per-family stability metrics
 * with severity badges, and plain-English interpretations for each family.
 * Includes CV method and generation timestamp for audit traceability.
 */

import { Card, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/provider";
import { getCvMethodLabel } from "@/lib/governance-labels";
import type { CvStats } from "@/types/api";

interface StabilityExplainabilityCardProps {
  cvMeanStd: Record<string, CvStats> | null;
  method: string | null;
  generatedAt: string | null;
  locale: string;
}

type StabilitySeverity = "stable" | "monitor" | "unstable";

const STABILITY_LABEL_KEYS: Record<StabilitySeverity, string> = {
  stable: "health.stability.stable",
  monitor: "health.stability.monitor",
  unstable: "health.stability.unstable",
};

const STABILITY_INTERPRET_KEYS: Record<StabilitySeverity, string> = {
  stable: "health.stability.interpretStable",
  monitor: "health.stability.interpretMonitor",
  unstable: "health.stability.interpretUnstable",
};

function getStabilitySeverity(std: number | null | undefined): StabilitySeverity {
  if (std == null) return "stable";
  if (std < 0.02) return "stable";
  if (std < 0.05) return "monitor";
  return "unstable";
}

function getSeverityColor(level: StabilitySeverity): string {
  if (level === "stable") return "bg-emerald-100 text-emerald-700";
  if (level === "monitor") return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

export function StabilityExplainabilityCard({ cvMeanStd, method, generatedAt, locale }: StabilityExplainabilityCardProps) {
  const { t } = useI18n();

  if (!cvMeanStd || Object.keys(cvMeanStd).length === 0) return null;

  const families = Object.entries(cvMeanStd);

  let overallSeverity: StabilitySeverity = "stable";
  for (const [, stats] of families) {
    const level = getStabilitySeverity(stats.pr_auc_std);
    if (level === "unstable") overallSeverity = "unstable";
    else if (level === "monitor" && overallSeverity === "stable") overallSeverity = "monitor";
  }

  const overallColor = overallSeverity === "stable"
    ? "bg-emerald-50 border-emerald-200 text-emerald-700"
    : overallSeverity === "monitor"
      ? "bg-amber-50 border-amber-200 text-amber-700"
      : "bg-red-50 border-red-200 text-red-700";

  const overallLabelKey = overallSeverity === "stable"
    ? "health.stability.stableOverall"
    : overallSeverity === "monitor"
      ? "health.stability.monitorOverall"
      : "health.stability.unstableOverall";

  return (
    <Card>
      <CardTitle>{t("health.cvStability")}</CardTitle>
      <p className="mt-1 text-xs text-slate-400">{t("health.stability.subtitle")}</p>

      <div className={`mt-4 rounded-lg border px-4 py-3 ${overallColor}`}>
        <p className="text-xs font-medium">{t(overallLabelKey)}</p>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-xs">
          <thead className="text-slate-500">
            <tr>
              <th className="px-2 py-1.5 font-medium">{t("health.cvFamily")}</th>
              <th className="px-2 py-1.5 font-medium">{t("health.cvPrAuc")}</th>
              <th className="px-2 py-1.5 font-medium">{t("health.cvPrAucSigma")}</th>
              <th className="px-2 py-1.5 font-medium">{t("health.stability.stability")}</th>
              <th className="px-2 py-1.5 font-medium">{t("health.stability.interpretation")}</th>
            </tr>
          </thead>
          <tbody>
            {families.map(([family, stats]) => {
              const level = getStabilitySeverity(stats.pr_auc_std);
              return (
                <tr key={family} className="border-t">
                  <td className="px-2 py-1.5 font-medium text-slate-700">{family}</td>
                  <td className="px-2 py-1.5 font-mono text-slate-600">{stats.pr_auc_mean?.toFixed(3) ?? "—"}</td>
                  <td className="px-2 py-1.5 font-mono text-slate-400">{stats.pr_auc_std?.toFixed(3) ?? "—"}</td>
                  <td className="px-2 py-1.5">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${getSeverityColor(level)}`}>
                      {t(STABILITY_LABEL_KEYS[level])}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-xs text-slate-500 max-w-[200px]">
                    {t(STABILITY_INTERPRET_KEYS[level])}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-400">
        {method && <span>{t("health.cvMethod", { method: getCvMethodLabel(method) })}</span>}
        {generatedAt && (
          <span>
            {t("health.cvGenerated", {
              date: new Date(generatedAt).toLocaleString(locale === "fa" ? "fa-IR-u-nu-latn" : "en-US"),
            })}
          </span>
        )}
      </div>
    </Card>
  );
}