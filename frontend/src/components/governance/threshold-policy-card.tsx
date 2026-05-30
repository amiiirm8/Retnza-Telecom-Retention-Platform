/**
 * Threshold Policy Card
 *
 * Detail view for a single threshold policy showing:
 * - Threshold value and role label
 * - Policy explanation and intended use
 * - Validation and test metrics (recall, precision, F1, FNR, lift, base rate)
 * - Business interpretation
 * - Raw calibration curve and confusion matrix in expandable drawers
 *
 * Policies with a recommended badge (primary_operating_policy) are highlighted
 * with an indigo ring. Missing metrics display role-appropriate explanations.
 */

import { Card, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/provider";
import { getPolicyRoleLabel, getPolicyBusinessInterpretation, getPolicyExplanation, getMissingMetricReason } from "@/lib/governance-labels";
import { formatMetric, formatThreshold } from "@/lib/governance-formatters";
import { JsonDrawer } from "@/components/ui/json-drawer";

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

interface ThresholdPolicyCardProps {
  policy: ThresholdPolicyEntry;
  isRecommended?: boolean;
}

export function ThresholdPolicyCard({ policy, isRecommended }: ThresholdPolicyCardProps) {
  const { t } = useI18n();
  const roleLabel = getPolicyRoleLabel(policy.role);
  const interpretation = getPolicyBusinessInterpretation(policy.role);
  const explanation = getPolicyExplanation(policy.role);
  const val = policy.metrics?.validation;
  const test = policy.metrics?.test;
  const hasCalibrationCurve = !!policy.calibration_curve;
  const hasConfusionMatrix = !!policy.confusion_matrix;
  const missingReason = getMissingMetricReason(policy.role);

  function renderMetric(value: number | null | undefined): string {
    if (value != null) return formatMetric(value);
    return missingReason;
  }

  return (
    <Card className={`${isRecommended ? "ring-2 ring-indigo-400" : ""}`}>
      <div className="flex items-start justify-between gap-2">
        <CardTitle>{roleLabel}</CardTitle>
        {isRecommended && (
          <span className="shrink-0 rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-medium text-indigo-700">
            {t("governance.thresholds.recommended")}
          </span>
        )}
      </div>

      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-2xl font-bold text-slate-900">{formatThreshold(policy.threshold)}</span>
        <span className="text-xs text-slate-400">{t("governance.thresholds.thresholdLabel")}</span>
      </div>

      {explanation && (
        <p className="mt-2 text-xs text-slate-600 leading-relaxed">{explanation}</p>
      )}

      <div className="mt-3 grid grid-cols-2 gap-4">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400 mb-1">{t("governance.validation")}</p>
          {val ? (
            <div className="space-y-1 text-xs">
              <MetricRow label="Recall" value={renderMetric(val.recall)} />
              <MetricRow label="Precision" value={renderMetric(val.precision)} />
              <MetricRow label="F1" value={renderMetric(val.f1)} />
              <MetricRow label="False Negative Rate" value={formatMetric(val.false_negative_rate)} />
              <MetricRow label="Lift" value={formatMetric(val.lift_at_threshold)} />
              <MetricRow label="Base Rate" value={formatMetric(val.base_rate)} />
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic">{missingReason}</p>
          )}
        </div>
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400 mb-1">{t("governance.test")}</p>
          {test ? (
            <div className="space-y-1 text-xs">
              <MetricRow label="Recall" value={renderMetric(test.recall)} />
              <MetricRow label="Precision" value={renderMetric(test.precision)} />
              <MetricRow label="F1" value={renderMetric(test.f1)} />
              <MetricRow label="False Negative Rate" value={formatMetric(test.false_negative_rate)} />
              <MetricRow label="Lift" value={formatMetric(test.lift_at_threshold)} />
              <MetricRow label="Base Rate" value={formatMetric(test.base_rate)} />
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic">{missingReason}</p>
          )}
        </div>
      </div>

      {interpretation && (
        <div className="mt-3 rounded-lg bg-indigo-50 px-3 py-2">
          <p className="text-[10px] font-medium text-indigo-700">{t("governance.businessInterpretation")}</p>
          <p className="mt-0.5 text-[10px] text-indigo-600 leading-relaxed">{interpretation}</p>
        </div>
      )}

      {hasCalibrationCurve || hasConfusionMatrix ? (
        <div className="mt-3 space-y-2">
          {hasCalibrationCurve && (
            <JsonDrawer label={t("governance.technical.rawCalibrationCurve")} data={policy.calibration_curve} />
          )}
          {hasConfusionMatrix && (
            <JsonDrawer label={t("governance.technical.rawConfusionMatrix")} data={policy.confusion_matrix} />
          )}
        </div>
      ) : null}
    </Card>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-500">{label}</span>
      <span className="font-mono text-xs text-slate-700">{value}</span>
    </div>
  );
}
