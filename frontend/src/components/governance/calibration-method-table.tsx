/**
 * Calibration Method Comparison Table
 *
 * Side-by-side comparison of all candidate calibration methods showing:
 * - Validation and test metrics (PR-AUC, Brier, ECE)
 * - Selected method highlighted with indigo background
 * - Recommended badge on the active selection
 * - Color-coded ECE values (green when < 0.05)
 *
 * Enables reviewers to evaluate the tradeoff between methods and understand
 * why the selected method was chosen for CRM production decisioning.
 */

import { Card, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/provider";
import { getCalibrationMethodLabel } from "@/lib/governance-labels";
import { formatMetric } from "@/lib/governance-formatters";

interface CalibrationMethodDetail {
  method: string;
  validation_pr_auc: number | null;
  validation_brier: number | null;
  validation_ece: number | null;
  test_pr_auc: number | null;
  test_brier: number | null;
  test_ece: number | null;
}

interface CalibrationMethodTableProps {
  methods: CalibrationMethodDetail[];
  selectedMethod: string;
}

export function CalibrationMethodTable({ methods, selectedMethod }: CalibrationMethodTableProps) {
  const { t } = useI18n();

  if (methods.length === 0) return null;

  return (
    <Card>
      <CardTitle>{t("governance.calibration.methodComparison")}</CardTitle>
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full text-left text-xs">
          <thead className="text-slate-500">
            <tr>
              <th className="px-2 py-1.5 font-medium">{t("governance.calibration.method")}</th>
              <th className="px-2 py-1.5 font-medium">{t("governance.calibration.valPrAuc")}</th>
              <th className="px-2 py-1.5 font-medium">{t("governance.calibration.valBrier")}</th>
              <th className="px-2 py-1.5 font-medium">{t("governance.calibration.valEce")}</th>
              <th className="px-2 py-1.5 font-medium">{t("governance.calibration.testPrAuc")}</th>
              <th className="px-2 py-1.5 font-medium">{t("governance.calibration.testBrier")}</th>
              <th className="px-2 py-1.5 font-medium">{t("governance.calibration.testEce")}</th>
            </tr>
          </thead>
          <tbody>
            {methods.map((m) => {
              const isSelected = m.method.toLowerCase() === selectedMethod.toLowerCase();
              return (
                <tr
                  key={m.method}
                  className={`border-t ${isSelected ? "bg-indigo-50 font-medium" : ""}`}
                >
                  <td className="px-2 py-1.5 text-slate-700">
                    <div className="flex items-center gap-1.5">
                      {getCalibrationMethodLabel(m.method)}
                      {isSelected && (
                        <span className="rounded-full bg-indigo-100 px-1.5 py-0.5 text-[9px] font-medium text-indigo-700">
                          {t("governance.thresholds.recommended")}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-2 py-1.5 font-mono">{m.validation_pr_auc != null ? formatMetric(m.validation_pr_auc, 4) : "—"}</td>
                  <td className="px-2 py-1.5 font-mono">{m.validation_brier != null ? formatMetric(m.validation_brier, 4) : "—"}</td>
                  <td className={`px-2 py-1.5 font-mono ${m.validation_ece != null && m.validation_ece < 0.05 ? "text-emerald-600" : ""}`}>
                    {m.validation_ece != null ? formatMetric(m.validation_ece, 4) : "—"}
                  </td>
                  <td className="px-2 py-1.5 font-mono">{m.test_pr_auc != null ? formatMetric(m.test_pr_auc, 4) : "—"}</td>
                  <td className="px-2 py-1.5 font-mono">{m.test_brier != null ? formatMetric(m.test_brier, 4) : "—"}</td>
                  <td className={`px-2 py-1.5 font-mono ${m.test_ece != null && m.test_ece < 0.05 ? "text-emerald-600" : ""}`}>
                    {m.test_ece != null ? formatMetric(m.test_ece, 4) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
