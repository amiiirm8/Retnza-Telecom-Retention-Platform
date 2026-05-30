/**
 * Calibration Educational Card
 *
 * Explains why calibration matters for CRM retention decisioning, including:
 * - Why raw model scores are not reliable as probabilities
 * - How calibration transforms scores into trustworthy risk estimates
 * - A concrete telecom business example (70% churn prediction scenario)
 * - Method comparison table with reliability, PR-AUC impact, overfit risk
 * - Monitoring warnings when ECE exceeds thresholds or overfit is detected
 *
 * This card serves both as education for non-technical executives and as
 * a monitoring tool for ML engineers overseeing calibration health.
 */

import { Card, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/provider";

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

interface CalibrationEducationalCardProps {
  selectedMethod: string;
  candidates: CalibrationMethodDetail[];
  validationPrAucCeiling: number | null;
}

export function CalibrationEducationalCard({ selectedMethod, candidates, validationPrAucCeiling }: CalibrationEducationalCardProps) {
  const { t } = useI18n();

  const selected = candidates.find((c) => c.method.toLowerCase() === selectedMethod.toLowerCase());

  const ece = selected?.validation_ece;
  const testPrAuc = selected?.test_pr_auc;
  const valPrAuc = selected?.validation_pr_auc;
  const overfit = selected?.overfit_risk;

  const eceWarning = ece != null && ece > 0.05 ? t("governance.calibrationEduc.warningEce") : null;
  const degradationWarning = valPrAuc != null && testPrAuc != null && (valPrAuc - testPrAuc) > 0.02
    ? t("governance.calibrationEduc.warningDegradation")
    : null;
  const overfitWarning = overfit === "medium" || overfit === "high"
    ? t("governance.calibrationEduc.warningOverfit")
    : null;
  const warnings = [eceWarning, degradationWarning, overfitWarning].filter(Boolean);

  return (
    <Card>
      <CardTitle>{t("governance.calibrationEduc.title")}</CardTitle>
      <p className="mt-1 text-xs text-slate-400">{t("governance.calibrationEduc.subtitle")}</p>

      <div className="mt-4 space-y-4">
        <div className="rounded-lg bg-indigo-50 px-4 py-3">
          <p className="text-xs font-medium text-indigo-700">{t("governance.calibrationEduc.whyCalibrate")}</p>
          <p className="mt-1 text-[10px] text-indigo-600 leading-relaxed">
            {t("governance.calibrationEduc.whyCalibrateDetail")}
          </p>
        </div>

        <div className="rounded-lg bg-slate-50 px-4 py-3">
          <p className="text-xs font-medium text-slate-700">{t("governance.calibrationEduc.businessExample")}</p>
          <p className="mt-1 text-[10px] text-slate-600 leading-relaxed">
            {t("governance.calibrationEduc.businessExampleDetail")}
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr>
                <th className="px-2 py-1.5 font-medium">{t("governance.calibrationEduc.tableMethod")}</th>
                <th className="px-2 py-1.5 font-medium">{t("governance.calibrationEduc.tableReliability")}</th>
                <th className="px-2 py-1.5 font-medium">{t("governance.calibrationEduc.tablePrAucImpact")}</th>
                <th className="px-2 py-1.5 font-medium">{t("governance.calibrationEduc.tableOverfit")}</th>
                <th className="px-2 py-1.5 font-medium">{t("governance.calibrationEduc.tableUse")}</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((m) => {
                const isSelected = m.method.toLowerCase() === selectedMethod.toLowerCase();
                const prAucDiff = m.validation_pr_auc != null && m.test_pr_auc != null
                  ? m.validation_pr_auc - m.test_pr_auc
                  : null;
                return (
                  <tr key={m.method} className={`border-t ${isSelected ? "bg-indigo-50 font-medium" : ""}`}>
                    <td className="px-2 py-1.5 text-slate-700">{m.method}</td>
                    <td className="px-2 py-1.5">
                      {m.test_ece != null && m.test_ece < 0.03
                        ? t("governance.calibrationEduc.reliabilityHigh")
                        : m.test_ece != null && m.test_ece < 0.08
                          ? t("governance.calibrationEduc.reliabilityMedium")
                          : t("governance.calibrationEduc.reliabilityLow")}
                    </td>
                    <td className="px-2 py-1.5 font-mono text-slate-600">
                      {prAucDiff != null
                        ? `${prAucDiff >= 0 ? "+" : ""}${prAucDiff.toFixed(4)}`
                        : "—"}
                    </td>
                    <td className="px-2 py-1.5">
                      {m.overfit_risk
                        ? t(`governance.calibration.overfit${m.overfit_risk.charAt(0).toUpperCase() + m.overfit_risk.slice(1)}` as unknown as string)
                        : "—"}
                    </td>
                    <td className="px-2 py-1.5 text-slate-500 max-w-[160px]">
                      {isSelected
                        ? t("governance.calibrationEduc.selectedUse")
                        : t("governance.calibrationEduc.availableAlternative")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {validationPrAucCeiling != null && (
          <div className="rounded-lg bg-slate-50 px-4 py-2">
            <p className="text-[10px] text-slate-500">
              {t("governance.calibrationEduc.ceilingNote", { ceiling: validationPrAucCeiling.toFixed(4) })}
            </p>
          </div>
        )}

        {warnings.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
            <p className="text-xs font-medium text-amber-700">{t("governance.calibrationEduc.monitoringWarnings")}</p>
            <ul className="mt-1 space-y-1">
              {warnings.map((w, i) => (
                <li key={i} className="flex gap-1.5 text-[10px] text-amber-600">
                  <span className="mt-0.5 h-1 w-1 shrink-0 rounded-full bg-amber-400" />
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
}
