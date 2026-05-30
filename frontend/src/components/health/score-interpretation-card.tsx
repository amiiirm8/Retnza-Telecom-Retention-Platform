/**
 * Score Interpretation Card
 *
 * Translates raw model performance metrics into business-facing explanations.
 * Each metric card shows:
 * - Current value with health status badge (Healthy / Monitor / Attention Needed)
 * - Business meaning — what the metric measures in plain English
 * - Telecom interpretation — what the value means for CRM retention operations
 * - Acceptable range — reference thresholds for evaluation
 *
 * Covers: PR-AUC, ROC-AUC, Brier Score, ECE with telecom-specific context
 * (e.g., "ECE > 0.10 means a subscriber at 70% predicted risk may actually
 * churn at 50% or 90%").
 */

import { Card, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/provider";
import { formatMetric } from "@/lib/governance-formatters";

interface ScoreRow {
  label: string;
  value: number | null;
  businessMeaning: string;
  telecomInterpretation: string;
  acceptableRange: string;
  isHealthy: boolean;
  isWarning: boolean;
  isCritical: boolean;
}

interface ScoreInterpretationCardProps {
  scores: ScoreRow[];
}

export function ScoreInterpretationCard({ scores }: ScoreInterpretationCardProps) {
  const { t } = useI18n();

  return (
    <Card>
      <CardTitle>{t("health.scoreInterpretation.title")}</CardTitle>
      <p className="mt-1 text-xs text-slate-400">{t("health.scoreInterpretation.subtitle")}</p>

      <div className="mt-4 space-y-3">
        {scores.map((s) => {
          let statusColor = "bg-emerald-50 border-emerald-200";
          let badgeColor = "bg-emerald-100 text-emerald-700";
          let statusLabel = t("health.scoreInterpretation.healthy");
          if (s.isWarning) {
            statusColor = "bg-amber-50 border-amber-200";
            badgeColor = "bg-amber-100 text-amber-700";
            statusLabel = t("health.scoreInterpretation.warning");
          }
          if (s.isCritical) {
            statusColor = "bg-red-50 border-red-200";
            badgeColor = "bg-red-100 text-red-700";
            statusLabel = t("health.scoreInterpretation.critical");
          }

          return (
            <div key={s.label} className={`rounded-lg border px-4 py-3 ${statusColor}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-medium text-slate-700">{s.label}</p>
                  <p className="mt-0.5 text-lg font-semibold text-slate-900">
                    {s.value != null ? formatMetric(s.value, 3) : "—"}
                  </p>
                </div>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${badgeColor}`}>
                  {statusLabel}
                </span>
              </div>
              <div className="mt-2 space-y-1 text-[10px] text-slate-500 leading-relaxed">
                <p><strong>{t("health.scoreInterpretation.businessMeaning")}:</strong> {s.businessMeaning}</p>
                <p><strong>{t("health.scoreInterpretation.telecomInterpretation")}:</strong> {s.telecomInterpretation}</p>
                <p><strong>{t("health.scoreInterpretation.acceptableRange")}:</strong> {s.acceptableRange}</p>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
