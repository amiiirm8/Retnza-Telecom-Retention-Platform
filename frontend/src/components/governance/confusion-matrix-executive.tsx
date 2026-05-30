/**
 * Executive Confusion Matrix
 *
 * 2×2 matrix with business-labeled quadrants replacing technical TP/FP/FN/TN:
 * - Correctly Identified Churners (TP)
 * - Incorrectly Flagged Loyal Customers (FP)
 * - Missed Churners (FN)
 * - Correctly Ignored Stable Customers (TN)
 *
 * Includes cost interpretation explaining the business impact of each outcome:
 * revenue saved from correct identifications, wasted outreach from false alarms,
 * lost revenue from missed churners, and capacity preserved from correct ignores.
 *
 * Falls back to metric-derived estimates when raw confusion matrix values
 * are not available from the threshold policy payload.
 */

import { Card, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/provider";

interface ConfusionMatrixValues {
  tp?: number;
  fp?: number;
  fn?: number;
  tn?: number;
}

interface ConfusionMatrixExecutiveProps {
  matrix: Record<string, unknown> | null | undefined;
  metrics: {
    precision: number;
    recall: number;
    base_rate: number;
  } | null;
}

export function ConfusionMatrixExecutive({ matrix, metrics }: ConfusionMatrixExecutiveProps) {
  const { t } = useI18n();

  const values: ConfusionMatrixValues = matrix
    ? {
        tp: typeof matrix.tp === "number" ? matrix.tp : undefined,
        fp: typeof matrix.fp === "number" ? matrix.fp : undefined,
        fn: typeof matrix.fn === "number" ? matrix.fn : undefined,
        tn: typeof matrix.tn === "number" ? matrix.tn : undefined,
      }
    : {};

  const hasValues = values.tp != null || values.fp != null || values.fn != null || values.tn != null;

  if (!hasValues && !metrics) return null;

  const businessLabels: Record<string, { label: string; description: string }> = {
    tp: {
      label: t("governance.confusionMatrix.tpLabel"),
      description: t("governance.confusionMatrix.tpDesc"),
    },
    fp: {
      label: t("governance.confusionMatrix.fpLabel"),
      description: t("governance.confusionMatrix.fpDesc"),
    },
    fn: {
      label: t("governance.confusionMatrix.fnLabel"),
      description: t("governance.confusionMatrix.fnDesc"),
    },
    tn: {
      label: t("governance.confusionMatrix.tnLabel"),
      description: t("governance.confusionMatrix.tnDesc"),
    },
  };

  const cellStyle = "rounded-lg px-4 py-3 text-center";
  const valueStyle = "text-2xl font-bold";
  const labelStyle = "mt-1 text-[10px] leading-relaxed";

  return (
    <Card>
      <CardTitle>{t("governance.confusionMatrix.title")}</CardTitle>
      <p className="mt-1 text-xs text-slate-400">{t("governance.confusionMatrix.description")}</p>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className={`${cellStyle} bg-emerald-50 border border-emerald-100`}>
          {hasValues ? (
            <>
              <p className={`${valueStyle} text-emerald-700`}>{values.tp ?? "—"}</p>
              <p className={`${labelStyle} text-emerald-600`}>
                <strong>{businessLabels.tp.label}</strong><br />
                {businessLabels.tp.description}
              </p>
            </>
          ) : metrics ? (
            <>
              <p className={`${valueStyle} text-emerald-700`}>~{(metrics.recall * 100).toFixed(0)}%</p>
              <p className={`${labelStyle} text-emerald-600`}>
                <strong>{businessLabels.tp.label}</strong><br />
                {businessLabels.tp.description}
              </p>
            </>
          ) : null}
        </div>

        <div className={`${cellStyle} bg-amber-50 border border-amber-100`}>
          {hasValues ? (
            <>
              <p className={`${valueStyle} text-amber-700`}>{values.fp ?? "—"}</p>
              <p className={`${labelStyle} text-amber-600`}>
                <strong>{businessLabels.fp.label}</strong><br />
                {businessLabels.fp.description}
              </p>
            </>
          ) : metrics ? (
            <>
              <p className={`${valueStyle} text-amber-700`}>~{((1 - metrics.precision) * 100).toFixed(0)}%</p>
              <p className={`${labelStyle} text-amber-600`}>
                <strong>{businessLabels.fp.label}</strong><br />
                {businessLabels.fp.description}
              </p>
            </>
          ) : null}
        </div>

        <div className={`${cellStyle} bg-red-50 border border-red-100`}>
          {hasValues ? (
            <>
              <p className={`${valueStyle} text-red-700`}>{values.fn ?? "—"}</p>
              <p className={`${labelStyle} text-red-600`}>
                <strong>{businessLabels.fn.label}</strong><br />
                {businessLabels.fn.description}
              </p>
            </>
          ) : metrics ? (
            <>
              <p className={`${valueStyle} text-red-700`}>~{((1 - metrics.recall) * 100).toFixed(0)}%</p>
              <p className={`${labelStyle} text-red-600`}>
                <strong>{businessLabels.fn.label}</strong><br />
                {businessLabels.fn.description}
              </p>
            </>
          ) : null}
        </div>

        <div className={`${cellStyle} bg-slate-50 border border-slate-100`}>
          {hasValues ? (
            <>
              <p className={`${valueStyle} text-slate-600`}>{values.tn ?? "—"}</p>
              <p className={`${labelStyle} text-slate-500`}>
                <strong>{businessLabels.tn.label}</strong><br />
                {businessLabels.tn.description}
              </p>
            </>
          ) : metrics ? (
            <>
              <p className={`${valueStyle} text-slate-600`}>~{((1 - metrics.base_rate) * 100).toFixed(0)}%</p>
              <p className={`${labelStyle} text-slate-500`}>
                <strong>{businessLabels.tn.label}</strong><br />
                {businessLabels.tn.description}
              </p>
            </>
          ) : null}
        </div>
      </div>

      <div className="mt-4 rounded-lg bg-slate-50 px-3 py-2">
        <p className="text-[10px] font-medium text-slate-600">{t("governance.confusionMatrix.costInterpretation")}</p>
        <ul className="mt-1 space-y-1 text-[10px] text-slate-500 leading-relaxed">
          <li>• {t("governance.confusionMatrix.costTp")}</li>
          <li>• {t("governance.confusionMatrix.costFp")}</li>
          <li>• {t("governance.confusionMatrix.costFn")}</li>
          <li>• {t("governance.confusionMatrix.costTn")}</li>
        </ul>
      </div>
    </Card>
  );
}
