/**
 * Policy Positioning Chart
 *
 * Scatter plot visualizing each threshold policy's recall vs precision tradeoff.
 * Enables executives to compare policy performance at a glance and identify
 * which policy offers the best balance for their operational priorities.
 *
 * Chart interpretation:
 * - Top-right = high recall + high precision (ideal, churners caught accurately)
 * - Bottom-right = high recall + low precision (catches churners but many false alarms)
 * - Top-left = low recall + high precision (few false alarms but misses churners)
 *
 * The recommended policy is highlighted with an indigo marker.
 */

"use client";

import { Card, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/provider";
import { getPolicyRoleLabel } from "@/lib/governance-labels";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ZAxis, Label,
} from "recharts";

interface PolicyMetrics {
  precision: number;
  recall: number;
}

interface PolicyPosition {
  role: string;
  threshold: number;
  metrics: PolicyMetrics | null;
}

interface PolicyPositioningChartProps {
  policies: PolicyPosition[];
  recommendedRole?: string;
}

export function PolicyPositioningChart({ policies, recommendedRole }: PolicyPositioningChartProps) {
  const { t } = useI18n();

  if (policies.length === 0) return null;

  const chartData = policies
    .filter((p) => p.metrics)
    .map((p) => ({
      name: getPolicyRoleLabel(p.role),
      role: p.role,
      recall: p.metrics!.recall * 100,
      precision: p.metrics!.precision * 100,
      threshold: p.threshold,
      isRecommended: p.role === recommendedRole,
    }));

  if (chartData.length === 0) return null;

  return (
    <Card>
      <CardTitle>{t("governance.positioning.title")}</CardTitle>
      <p className="mt-1 text-xs text-slate-400">{t("governance.positioning.description")}</p>
      <div className="mt-3" dir="ltr">
        <ResponsiveContainer width="100%" height={280}>
          <ScatterChart margin={{ top: 20, right: 20, bottom: 30, left: 40 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="recall"
              domain={[0, 100]}
              tick={{ fontSize: 10 }}
              tickFormatter={(v) => `${v.toFixed(0)}%`}
            >
              <Label value={t("governance.positioning.recallAxis")} position="bottom" offset={0} style={{ fontSize: 10, fill: "#94a3b8" }} />
            </XAxis>
            <YAxis
              dataKey="precision"
              domain={[0, 100]}
              tick={{ fontSize: 10 }}
              tickFormatter={(v) => `${v.toFixed(0)}%`}
            >
              <Label value={t("governance.positioning.precisionAxis")} angle={-90} position="left" offset={0} style={{ fontSize: 10, fill: "#94a3b8" }} />
            </YAxis>
            <ZAxis range={[80, 80]} />
            <Tooltip
              formatter={(value: unknown) => {
                const num = typeof value === "number" ? value : 0;
                return `${num.toFixed(1)}%`;
              }}
              labelFormatter={(label: unknown) => String(label)}
            />
            <Scatter
              data={chartData}
              fill="#4f46e5"
              stroke="#3730a3"
              strokeWidth={1}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 space-y-1.5">
        {chartData.map((point) => (
          <div key={point.role} className="flex items-center gap-2 text-[10px]">
            <span
              className={`h-2.5 w-2.5 shrink-0 rounded-full ${point.isRecommended ? "bg-indigo-500 ring-2 ring-indigo-200" : "bg-slate-300"}`}
            />
            <span className="font-medium text-slate-700">{point.name}</span>
            <span className="text-slate-400">
              R={point.recall.toFixed(0)}% P={point.precision.toFixed(0)}%
            </span>
            {point.isRecommended && (
              <span className="rounded-full bg-indigo-100 px-1.5 py-0.5 text-[9px] font-medium text-indigo-700">
                {t("governance.thresholds.recommended")}
              </span>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
