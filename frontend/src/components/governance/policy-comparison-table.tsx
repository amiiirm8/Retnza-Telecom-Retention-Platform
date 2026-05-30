/**
 * Policy Comparison Table
 *
 * Side-by-side comparison of all configured threshold policies showing:
 * - Policy name and intended use
 * - Threshold value
 * - Validation metrics (recall, precision, F1)
 * - Recommended badge for the active operating policy
 *
 * This enables executives to compare tradeoffs between policies at a glance
 * and understand which policy is recommended for production use.
 */

import { Card, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/provider";
import { getPolicyRoleLabel, getPolicyIntendedUse, getMissingMetricReason } from "@/lib/governance-labels";
import { formatMetric, formatThreshold } from "@/lib/governance-formatters";

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
}

interface PolicyComparisonTableProps {
  policies: ThresholdPolicyEntry[];
  recommendedRole?: string;
}

export function PolicyComparisonTable({ policies, recommendedRole }: PolicyComparisonTableProps) {
  const { t } = useI18n();

  if (policies.length === 0) return null;

  function renderMetric(value: number | null | undefined, missingReason: string): string {
    if (value != null) return formatMetric(value);
    return missingReason;
  }

  return (
    <Card>
      <CardTitle>{t("governance.comparison.title")}</CardTitle>
      <p className="mt-1 text-xs text-slate-400">{t("governance.comparison.description")}</p>
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full text-left text-xs">
          <thead className="text-slate-500">
            <tr>
              <th className="px-2 py-1.5 font-medium">{t("governance.comparison.policy")}</th>
              <th className="px-2 py-1.5 font-medium">{t("governance.comparison.threshold")}</th>
              <th className="px-2 py-1.5 font-medium">{t("governance.comparison.recall")}</th>
              <th className="px-2 py-1.5 font-medium">{t("governance.comparison.precision")}</th>
              <th className="px-2 py-1.5 font-medium">{t("governance.comparison.f1")}</th>
              <th className="px-2 py-1.5 font-medium">{t("governance.comparison.intendedUse")}</th>
            </tr>
          </thead>
          <tbody>
            {policies.map((p) => {
              const isRec = recommendedRole === p.role;
              const missingReason = getMissingMetricReason(p.role);
              const valMetrics = p.metrics?.validation;
              return (
                <tr
                  key={p.role}
                  className={`border-t ${isRec ? "bg-indigo-50" : ""}`}
                >
                  <td className="px-2 py-1.5 font-medium text-slate-700">
                    <div className="flex items-center gap-1.5">
                      {getPolicyRoleLabel(p.role)}
                      {isRec && (
                        <span className="rounded-full bg-indigo-100 px-1.5 py-0.5 text-[9px] font-medium text-indigo-700">
                          {t("governance.thresholds.recommended")}
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-[9px] text-slate-400">{getPolicyIntendedUse(p.role)}</p>
                  </td>
                  <td className="px-2 py-1.5 font-mono text-slate-600">{formatThreshold(p.threshold)}</td>
                  <td className="px-2 py-1.5">{renderMetric(valMetrics?.recall ?? null, missingReason)}</td>
                  <td className="px-2 py-1.5">{renderMetric(valMetrics?.precision ?? null, missingReason)}</td>
                  <td className="px-2 py-1.5">{renderMetric(valMetrics?.f1 ?? null, missingReason)}</td>
                  <td className="px-2 py-1.5 text-slate-500 max-w-[200px]">{getPolicyIntendedUse(p.role)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
