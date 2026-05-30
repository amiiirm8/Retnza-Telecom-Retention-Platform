/**
 * Calibration Summary Card
 *
 * Summarizes the calibration method selection, candidate methods evaluated,
 * validation PR-AUC ceiling, and overfit risk assessment. Displays the
 * selection rationale explaining why the chosen method was preferred for
 * CRM decisioning, along with tradeoff notes and monitoring recommendations.
 */

import { Card, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/provider";
import { getCalibrationMethodLabel, getCalibrationExplanation } from "@/lib/governance-labels";
import { formatMetric } from "@/lib/governance-formatters";
import { JsonDrawer } from "@/components/ui/json-drawer";

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

interface CalibrationSummaryCardProps {
  selectedMethod: string;
  prAucValidationCeiling: number | null;
  candidates: CalibrationMethodDetail[];
  rawSummary?: Record<string, unknown> | null;
}

export function CalibrationSummaryCard({
  selectedMethod,
  prAucValidationCeiling,
  candidates,
  rawSummary,
}: CalibrationSummaryCardProps) {
  const { t } = useI18n();
  const selected = candidates.find((c) => c.method.toLowerCase() === selectedMethod.toLowerCase());

  const overfitLabels: Record<string, string> = {
    low: t("governance.calibration.overfitLow"),
    medium: t("governance.calibration.overfitMedium"),
    high: t("governance.calibration.overfitHigh"),
  };

  const overfitRisk = selected?.overfit_risk
    ? overfitLabels[selected.overfit_risk.toLowerCase()] || selected.overfit_risk
    : null;

  const explanation = getCalibrationExplanation(selectedMethod);

  return (
    <Card>
      <CardTitle>{t("governance.calibration.health")}</CardTitle>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.calibration.selectedMethod")}</p>
          <p className="mt-0.5 text-sm font-semibold text-slate-800">{getCalibrationMethodLabel(selectedMethod)}</p>
        </div>

        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.calibration.candidates")}</p>
          <p className="mt-0.5 text-sm font-semibold text-slate-800">
            {candidates.map((c) => getCalibrationMethodLabel(c.method)).join(", ")}
          </p>
        </div>

        {prAucValidationCeiling != null && (
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.calibration.validationPrAuc")}</p>
            <p className="mt-0.5 text-sm font-semibold text-slate-800">{formatMetric(prAucValidationCeiling, 4)}</p>
          </div>
        )}

        {overfitRisk && (
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{t("governance.calibration.overfitRisk")}</p>
            <p className="mt-0.5 text-sm font-semibold text-slate-800">{overfitRisk}</p>
          </div>
        )}
      </div>

      {selected && (
        <div className="mt-3 rounded-lg bg-indigo-50 px-3 py-2">
          <p className="text-[10px] font-medium text-indigo-700">{t("governance.calibration.selectionRationale")}</p>
          <p className="mt-0.5 text-[10px] text-indigo-600 leading-relaxed">{explanation}</p>
        </div>
      )}

      {selected && (
        <div className="mt-3 rounded-lg bg-indigo-50/50 px-3 py-2">
          <p className="text-[10px] font-medium text-indigo-700">{t("governance.calibration.tradeoff")}</p>
          <p className="mt-0.5 text-[10px] text-indigo-600 leading-relaxed">
            {t("governance.calibration.preferredForCrm")}
          </p>
          <p className="mt-1 text-[10px] text-amber-600 leading-relaxed">
            {t("governance.calibration.monitoringRecommended")}
          </p>
        </div>
      )}

      {rawSummary && Object.keys(rawSummary).length > 0 && (
        <div className="mt-3">
          <JsonDrawer label={t("governance.technical.rawSummary")} data={rawSummary} />
        </div>
      )}
    </Card>
  );
}
