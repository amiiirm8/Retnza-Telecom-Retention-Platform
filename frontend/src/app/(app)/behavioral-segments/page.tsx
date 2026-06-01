"use client";

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Legend,
  ReferenceLine,
} from "recharts";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { ChartWrapper } from "@/components/ui/chart-wrapper";
import { PageLoading } from "@/components/ui/loading";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { useI18n } from "@/i18n/provider";
import { formatNumber, formatPercent } from "@/lib/format";

const SEGMENT_COLORS = ["#4f46e5", "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#6366f1"];

interface DistinguishingFeature {
  feature: string;
  label: string;
  z_score: number;
  deviation: number;
  direction: string;
}

interface BehavioralProfile {
  cluster_id: number;
  name: string;
  short_summary: string;
  size: number;
  size_pct: number;
  mean_calibrated_risk: number;
  churn_risk_ratio: number;
  high_risk_pct: number;
  churn_rate: number | null;
  risk_vs_average: string;
  operational_interpretation: string;
  retention_posture: string;
  priority_level: string;
  treatment: string;
  primary_channel: string;
  features: Record<string, number>;
  top_distinguishing_features: DistinguishingFeature[];
}

interface BehavioralSegmentsSummary {
  schema_version: string;
  generated_at: string;
  n_clusters: number;
  selected_method: string;
  selected_k: number;
  method_selection_rationale: string;
  scientific_context: string;
  features_used: string[];
  feature_labels: Record<string, string>;
  overall_mean_risk: number;
  metrics: {
    silhouette_score: number;
    davies_bouldin: number;
    calinski_harabasz: number;
  };
  stability: {
    mean_ari: number;
    std_ari: number;
    n_seeds: number;
  };
  method_comparison: Record<string, {
    best_k: number;
    silhouette_score: number;
    davies_bouldin: number;
    calinski_harabasz: number;
  }>;
  limitations: string[];
  profiles: BehavioralProfile[];
  highest_risk_segment: { name: string; mean_calibrated_risk: number } | null;
  lowest_risk_segment: { name: string; mean_calibrated_risk: number } | null;
  narrative: string;
  error?: string;
}

function priorityBadge(level: string) {
  const map: Record<string, { bg: string; text: string }> = {
    critical: { bg: "bg-red-100", text: "text-red-700" },
    high: { bg: "bg-orange-100", text: "text-orange-700" },
    medium: { bg: "bg-yellow-100", text: "text-yellow-700" },
    low: { bg: "bg-green-100", text: "text-green-700" },
  };
  const s = map[level] || map.low;
  return `${s.bg} ${s.text}`;
}

function riskBadge(risk: number, avg: number) {
  if (risk > avg * 1.15) return "bg-red-50 text-red-600 border-red-200";
  if (risk < avg * 0.85) return "bg-green-50 text-green-600 border-green-200";
  return "bg-yellow-50 text-yellow-600 border-yellow-200";
}

export default function BehavioralSegmentsPage() {
  const { t, dir, locale } = useI18n();
  const [data, setData] = useState<BehavioralSegmentsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCluster, setSelectedCluster] = useState<number | null>(null);

  useEffect(() => {
    api<BehavioralSegmentsSummary>("/behavioral-segments/summary")
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <PageLoading />;

  if (!data || data.error || !data.profiles || data.profiles.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-4" dir={dir}>
        <p className="text-lg text-slate-500">{data?.error || t("behavioralSegments.noData")}</p>
      </div>
    );
  }

  const profiles = data.profiles;
  const selectedProfile = selectedCluster != null
    ? profiles.find(p => p.cluster_id === selectedCluster)
    : null;

  // Chart data builders.
  const distributionData = profiles.map(p => ({
    name: p.name,
    count: p.size,
  }));

  const riskData = profiles.map(p => ({
    name: p.name,
    risk: +(p.mean_calibrated_risk * 100).toFixed(1),
    churn: p.churn_rate != null ? +(p.churn_rate * 100).toFixed(1) : null,
    ratio: +(p.churn_risk_ratio).toFixed(1),
  }));

  const overallRiskPct = +(data.overall_mean_risk * 100).toFixed(1);

  // Radar chart data (normalised 0-100).
  const featureKeys = Object.keys(profiles[0]?.features || {});
  const featureLabels = data.feature_labels || {};
  const maxValues: Record<string, number> = {};
  featureKeys.forEach(key => {
    maxValues[key] = Math.max(...profiles.map(p => p.features[key] ?? 0));
    if (maxValues[key] === 0) maxValues[key] = 1;
  });
  const radarData = featureKeys.map(key => {
    const label = featureLabels[key] || key.replace(/_/g, " ");
    const dataPoint: Record<string, string | number> = { subject: label };
    profiles.forEach(p => {
      dataPoint[p.name] = ((p.features[key] ?? 0) / maxValues[key]) * 100;
    });
    return dataPoint;
  });

  const methodKeys = Object.keys(data.method_comparison || {});

  return (
    <div className="space-y-6" dir={dir}>
      {/* Header */}
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t("behavioralSegments.title")}</h1>
          <p className="mt-1 text-sm text-slate-500">{t("behavioralSegments.subtitle")}</p>
        </div>
        {data.generated_at && (
          <span className="text-xs text-slate-400 hidden sm:block">
            {new Date(data.generated_at).toLocaleDateString(locale === "fa" ? "fa-IR" : "en-US", {
              year: "numeric", month: "short", day: "numeric",
            })}
          </span>
        )}
      </header>

      {/* Summary Banner */}
      <Card className="bg-gradient-to-r from-indigo-50 to-blue-50 border-indigo-100">
        <div className="p-5 space-y-4">
          <p className="text-sm text-slate-700 leading-relaxed">{data.narrative}</p>
          <div className="flex flex-wrap gap-x-6 gap-y-2 pt-3 text-xs text-slate-500 border-t border-indigo-100">
            <span><strong>{t("behavioralSegments.selectedMethod")}:</strong> {data.selected_method} (k={data.selected_k})</span>
            <span><strong>{t("behavioralSegments.silhouette")}:</strong> {data.metrics.silhouette_score.toFixed(3)}</span>
            <span><strong>{t("behavioralSegments.daviesBouldin")}:</strong> {data.metrics.davies_bouldin.toFixed(3)}</span>
            <span><strong>{t("behavioralSegments.calinskiHarabasz")}:</strong> {data.metrics.calinski_harabasz.toFixed(0)}</span>
            <span><strong>{t("behavioralSegments.stability")}:</strong> ARI = {data.stability.mean_ari.toFixed(3)}</span>
            <span><strong>{t("behavioralSegments.features")}:</strong> {data.features_used.length} {t("common.dimensions")}</span>
          </div>
        </div>
      </Card>

      {/* Insight Callout Cards */}
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-red-200 bg-red-50 p-3">
          <p className="text-xs font-semibold text-red-700 uppercase tracking-wide">{t("behavioralSegments.highestRisk")}</p>
          {data.highest_risk_segment && (
            <>
              <p className="text-sm font-bold text-red-800 mt-1">{data.highest_risk_segment.name}</p>
              <p className="text-xs text-red-600 mt-0.5">
                {formatPercent(data.highest_risk_segment.mean_calibrated_risk, locale)} —
                {data.lowest_risk_segment && data.lowest_risk_segment.mean_calibrated_risk > 0
                  ? ` ${(data.highest_risk_segment.mean_calibrated_risk / data.lowest_risk_segment.mean_calibrated_risk).toFixed(1)}× ${t("behavioralSegments.baseAverage")}`
                  : ""}
              </p>
            </>
          )}
        </div>
        <div className="rounded-lg border border-green-200 bg-green-50 p-3">
          <p className="text-xs font-semibold text-green-700 uppercase tracking-wide">{t("behavioralSegments.lowestRisk")}</p>
          {data.lowest_risk_segment && (
            <>
              <p className="text-sm font-bold text-green-800 mt-1">{data.lowest_risk_segment.name}</p>
              <p className="text-xs text-green-600 mt-0.5">
                {formatPercent(data.lowest_risk_segment.mean_calibrated_risk, locale)}
              </p>
            </>
          )}
        </div>
        <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3">
          <p className="text-xs font-semibold text-indigo-700 uppercase tracking-wide">{t("behavioralSegments.overallAvg")}</p>
          <p className="text-sm font-bold text-indigo-800 mt-1">{formatPercent(data.overall_mean_risk, locale)}</p>
          <p className="text-xs text-indigo-600 mt-0.5">{t("behavioralSegments.meanCalibratedRisk")}</p>
        </div>
      </div>

      {/* Cluster Cards */}
      <ErrorBoundary section="Segment Cards">
        <h2 className="text-lg font-bold text-slate-800">{t("behavioralSegments.segmentSummary")}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {profiles.map((seg, idx) => (
            <div
              key={seg.cluster_id}
              className={`rounded-xl border border-slate-200 bg-white shadow-sm transition-all cursor-pointer hover:shadow-md ${
                selectedCluster === seg.cluster_id ? "ring-2 ring-indigo-400" : ""
              }`}
              style={{ borderTop: `4px solid ${SEGMENT_COLORS[idx % SEGMENT_COLORS.length]}` }}
              onClick={() => setSelectedCluster(selectedCluster === seg.cluster_id ? null : seg.cluster_id)}
            >
              <div className="p-4 space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="text-base font-bold text-slate-800 leading-tight">{seg.name}</h3>
                    <p className="text-sm text-slate-500 mt-0.5">
                      {formatNumber(seg.size, locale)} {t("common.subscribers")}{" "}
                      <span className="text-xs">({(seg.size_pct * 100).toFixed(1)}%)</span>
                    </p>
                  </div>
                  <span className={`shrink-0 text-xs font-semibold px-2 py-1 rounded ${priorityBadge(seg.priority_level)}`}>
                    {seg.priority_level.charAt(0).toUpperCase() + seg.priority_level.slice(1)}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 border-y border-slate-100 py-2">
                  <div>
                    <p className="text-xs text-slate-500">{t("behavioralSegments.meanRisk")}</p>
                    <p className={`text-sm font-bold ${riskBadge(seg.mean_calibrated_risk, data.overall_mean_risk)} inline-block px-1.5 py-0.5 rounded border`}>
                      {formatPercent(seg.mean_calibrated_risk, locale)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">{t("behavioralSegments.churnRate")}</p>
                    <p className="text-sm font-semibold text-slate-900">
                      {seg.churn_rate != null ? formatPercent(seg.churn_rate, locale) : t("common.unknown")}
                    </p>
                  </div>
                </div>

                <p className="text-xs text-slate-600 leading-relaxed line-clamp-2">
                  {seg.short_summary}
                </p>

                <p className="text-xs text-indigo-700 bg-indigo-50 p-2 rounded leading-relaxed">
                  {seg.retention_posture}
                </p>
              </div>
            </div>
          ))}
        </div>
      </ErrorBoundary>

      {/* Selected Cluster Detail */}
      {selectedProfile && (
        <ErrorBoundary section="Segment Detail">
          <Card className="border-indigo-200 bg-indigo-50/30">
            <div className="p-5 space-y-4">
              <div className="flex items-start justify-between">
                <h3 className="text-lg font-bold text-slate-800">{selectedProfile.name}</h3>
                <button
                  onClick={() => setSelectedCluster(null)}
                  className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
                >
                  ✕
                </button>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-700 mb-1">{t("behavioralSegments.whatThisMeans")}</p>
                    <p className="text-sm text-slate-600 leading-relaxed">
                      {selectedProfile.operational_interpretation}
                    </p>
                  </div>
                  {selectedProfile.churn_risk_ratio && (
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-slate-500">{t("behavioralSegments.churnRiskRatio")}:</span>
                      <span className={`font-bold ${
                        selectedProfile.churn_risk_ratio > 1 ? "text-red-600" : "text-green-600"
                      }`}>
                        {selectedProfile.churn_risk_ratio.toFixed(1)}×
                      </span>
                      <span className="text-slate-400">
                        {selectedProfile.churn_risk_ratio > 1
                          ? t("behavioralSegments.aboveAverage")
                          : t("behavioralSegments.belowAverage")}
                      </span>
                    </div>
                  )}
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-500">{t("behavioralSegments.priorityLevel")}</span>
                    <span className={`font-semibold ${priorityBadge(selectedProfile.priority_level).replace("bg-", "text-").replace("100", "600")}`}>
                      {selectedProfile.priority_level.charAt(0).toUpperCase() + selectedProfile.priority_level.slice(1)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-500">{t("behavioralSegments.primaryChannel")}</span>
                    <span className="font-semibold text-slate-700">{selectedProfile.primary_channel}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-500">{t("behavioralSegments.treatment")}</span>
                    <span className="font-semibold text-slate-700 text-right max-w-[60%]">{selectedProfile.treatment}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-500">{t("behavioralSegments.posture")}</span>
                    <span className="font-semibold text-indigo-700 text-right max-w-[60%]">{selectedProfile.retention_posture}</span>
                  </div>
                </div>
              </div>

              {/* Distinguishing Features */}
              <div>
                <p className="text-sm font-semibold text-slate-700 mb-2">{t("behavioralSegments.distinguishingFeatures")}</p>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {selectedProfile.top_distinguishing_features.slice(0, 5).map((ft) => (
                    <div key={ft.feature} className="flex items-center justify-between bg-white rounded p-2 border border-slate-200">
                      <span className="text-xs text-slate-600">{ft.label}</span>
                      <span className={`text-xs font-mono font-medium ml-2 ${
                        ft.direction === "above" ? "text-orange-600" : "text-blue-600"
                      }`}>
                        z = {ft.z_score.toFixed(2)} {ft.direction === "above" ? "↑" : "↓"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        </ErrorBoundary>
      )}

      {/* Charts Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        <ErrorBoundary section="Segment Distribution">
          <ChartWrapper title={t("behavioralSegments.segmentDistribution")} className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={distributionData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-15} textAnchor="end" height={60} />
                <YAxis tickFormatter={(v) => formatNumber(v, locale)} />
                <Tooltip
                  formatter={(value: unknown) => [formatNumber(value as number, locale), t("behavioralSegments.clusterSize")]}
                  labelFormatter={(label: unknown) => String(label)}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {distributionData.map((_d, idx) => (
                    <Cell key={idx} fill={SEGMENT_COLORS[idx % SEGMENT_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartWrapper>
        </ErrorBoundary>

        <ErrorBoundary section="Risk Comparison">
          <ChartWrapper title={t("behavioralSegments.riskComparison")} className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={riskData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-15} textAnchor="end" height={60} />
                <YAxis domain={[0, 'auto']} tickFormatter={(v) => `${v}%`} />
                <Tooltip
                  formatter={(value: unknown, name: unknown) => [
                    `${(value as number).toFixed(1)}%`,
                    name === "risk" ? t("behavioralSegments.meanRisk") : t("behavioralSegments.churnRate"),
                  ]}
                />
                <ReferenceLine
                  y={overallRiskPct}
                  stroke="#94a3b8"
                  strokeDasharray="4 4"
                  label={{ value: `${t("behavioralSegments.overallAvg")} ${overallRiskPct}%`, position: "right", fontSize: 10, fill: "#94a3b8" }}
                />
                {riskData.map((_d, idx) => (
                  <Bar key={idx} dataKey="risk" radius={[4, 4, 0, 0]} fill={SEGMENT_COLORS[idx % SEGMENT_COLORS.length]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </ChartWrapper>
        </ErrorBoundary>
      </div>

      {/* Radar Chart */}
      <ErrorBoundary section="Feature Profile Radar">
        <ChartWrapper title={t("behavioralSegments.featureRadar")} className="h-96 bg-white">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="subject" tick={{ fill: "#64748b", fontSize: 11 }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} />
                <Tooltip
                  formatter={(value: unknown, name: unknown) => [`${(value as number).toFixed(0)}% (normalised)`, String(name)]}
                />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              {profiles.map((p, idx) => (
                <Radar
                  key={p.name}
                  name={p.name}
                  dataKey={p.name}
                  stroke={SEGMENT_COLORS[idx % SEGMENT_COLORS.length]}
                  fill={SEGMENT_COLORS[idx % SEGMENT_COLORS.length]}
                  fillOpacity={0.08}
                  strokeWidth={2}
                />
              ))}
            </RadarChart>
          </ResponsiveContainer>
        </ChartWrapper>
      </ErrorBoundary>

      {/* Methodology Section */}
      <ErrorBoundary section="Methodology">
        <Card>
          <div className="p-5 space-y-5">
            <h3 className="text-lg font-bold text-slate-800">{t("behavioralSegments.methodology")}</h3>

            {/* Scientific Context */}
            <p className="text-sm text-slate-600 leading-relaxed">
              {data.scientific_context}
            </p>

            {/* Method Rationale */}
            <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">{t("behavioralSegments.methodSelection")}</p>
              <p className="text-sm text-slate-700 leading-relaxed">{data.method_selection_rationale}</p>
            </div>

            {/* Method Comparison Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-slate-600">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="text-left py-2 font-medium">{t("behavioralSegments.selectedMethod")}</th>
                    <th className="text-right py-2 font-medium">K</th>
                    <th className="text-right py-2 font-medium">{t("behavioralSegments.silhouette")}</th>
                    <th className="text-right py-2 font-medium">{t("behavioralSegments.daviesBouldin")}</th>
                    <th className="text-right py-2 font-medium">{t("behavioralSegments.calinskiHarabasz")}</th>
                  </tr>
                </thead>
                <tbody>
                  {methodKeys.map(m => (
                    <tr key={m} className={`border-b border-slate-100 ${
                      m === data.selected_method ? "bg-indigo-50 font-semibold" : ""
                    }`}>
                      <td className="py-2">
                        {m === data.selected_method ? `★ ${m}` : m}
                      </td>
                      <td className="text-right py-2">{data.method_comparison[m]?.best_k}</td>
                      <td className="text-right py-2">{data.method_comparison[m]?.silhouette_score?.toFixed(3)}</td>
                      <td className="text-right py-2">{data.method_comparison[m]?.davies_bouldin?.toFixed(3)}</td>
                      <td className="text-right py-2">{data.method_comparison[m]?.calinski_harabasz?.toFixed(0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Features Used */}
            <div>
              <p className="text-xs font-medium text-slate-500 mb-2">{t("behavioralSegments.features")} ({data.features_used.length}):</p>
              <div className="flex flex-wrap gap-1.5">
                {data.features_used.map(f => (
                  <span key={f} className="text-xs bg-slate-100 text-slate-600 rounded px-2 py-0.5">
                    {data.feature_labels?.[f] || f}
                  </span>
                ))}
              </div>
            </div>

            {/* Limitations */}
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">{t("behavioralSegments.limitations")}</p>
              <ul className="space-y-1.5">
                {(data.limitations || []).map((lim, i) => (
                  <li key={i} className="text-xs text-slate-500 flex gap-2">
                    <span className="text-slate-300 mt-0.5">•</span>
                    <span>{lim}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Card>
      </ErrorBoundary>
    </div>
  );
}
