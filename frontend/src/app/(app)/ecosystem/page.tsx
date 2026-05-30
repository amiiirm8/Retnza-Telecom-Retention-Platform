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
} from "recharts";
import { api } from "@/lib/api";
import { Card, CardTitle } from "@/components/ui/card";
import { ChartWrapper } from "@/components/ui/chart-wrapper";
import { PageLoading } from "@/components/ui/loading";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { useI18n } from "@/i18n/provider";
import { getExecutiveEcosystemSegment } from "@/lib/label-resolver";
import { formatNumber } from "@/lib/format";
import type { EcosystemSummary, EcosystemSegments, AdoptionMetric } from "@/types/api";
const SEGMENT_COLORS = ["#4f46e5", "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#6366f1"];

const RAW_SEGMENT_KEYS = [
  "non_ecosystem",
  "volte_only",
  "rubika_only",
  "ewano_only",
  "hamrahman_only",
  "partial_ecosystem",
  "fully_adopted",
];

export default function EcosystemPage() {
  const { t, dir, locale } = useI18n();
  const [summary, setSummary] = useState<EcosystemSummary | null>(null);
  const [segments, setSegments] = useState<EcosystemSegments | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api<EcosystemSummary>("/ecosystem/summary"),
      api<EcosystemSegments>("/ecosystem/segments"),
    ])
      .then(([s, seg]) => {
        setSummary(s);
        setSegments(seg);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <PageLoading />;

  const adoptionMetrics: { key: string; labelKey: string; data: AdoptionMetric | undefined }[] = [
    { key: "rubika", labelKey: "ecosystem.rubika", data: summary?.rubika_adoption },
    { key: "ewano", labelKey: "ecosystem.ewano", data: summary?.ewano_adoption },
    { key: "hamrahman", labelKey: "ecosystem.hamrahMan", data: summary?.hamrah_man_engagement },
    { key: "volte", labelKey: "ecosystem.volte", data: summary?.volte_usage },
  ];

  const allSegments = segments?.segments || [];
  const segmentChartData = allSegments.map((s) => ({
    name: getExecutiveEcosystemSegment(s.ecosystem_segment),
    count: s.n,
    risk: s.mean_calibrated_risk != null ? +(s.mean_calibrated_risk * 100).toFixed(1) : null,
    wording: s.wording,
  }));

  const funnelChartData = segmentChartData
    .filter((d) => RAW_SEGMENT_KEYS.some((key) => {
      const execLabel = getExecutiveEcosystemSegment(key).toLowerCase();
      return d.name.toLowerCase() === execLabel || d.name.toLowerCase().includes(key.replace(/_/g, " "));
    }))
    .sort((a, b) => b.count - a.count);

  const highestRiskSegment = [...segmentChartData].sort((a, b) => (b.risk ?? 0) - (a.risk ?? 0))[0];
  const nonEcoData = segmentChartData.find((d) => d.name === getExecutiveEcosystemSegment("non_ecosystem"));
  const embeddedData = segmentChartData.find((d) => d.name === getExecutiveEcosystemSegment("fully_adopted"));

  const storyItems: { icon: string; text: string }[] = [];

  if (embeddedData && nonEcoData && embeddedData.risk != null && nonEcoData.risk != null) {
    const delta = (nonEcoData.risk - embeddedData.risk).toFixed(1);
    storyItems.push({
      icon: "📊",
      text: t("ecosystem.story.segmentContrast", { delta: `${delta}%` }),
    });
  }

  const largestInactiveGap = adoptionMetrics
    .map((m) => ({ product: m.key, count: m.data?.inactive_capable_n ?? 0, labelKey: m.labelKey }))
    .sort((a, b) => b.count - a.count)[0];

  if (largestInactiveGap && largestInactiveGap.count > 0) {
    storyItems.push({
      icon: "🎯",
      text: t("ecosystem.story.adoptionGap", {
        product: t(largestInactiveGap.labelKey),
        count: formatNumber(largestInactiveGap.count, locale),
      }),
    });
  }

  return (
    <div className="space-y-6" dir={dir}>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">{t("ecosystem.title")}</h1>
        <p className="mt-1 text-sm italic text-slate-500">
          {summary?.disclaimer}
        </p>
      </header>

      {storyItems.length > 0 && (
        <Card className="border-emerald-200 bg-gradient-to-br from-emerald-50 to-white">
          <h2 className="text-base font-bold text-emerald-900">{t("ecosystem.segments.riskBySegment")}</h2>
          <div className="mt-3 space-y-2">
            {storyItems.map((item, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <span className="shrink-0">{item.icon}</span>
                <span>{item.text}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {adoptionMetrics.map(({ key, labelKey, data }) => data ? (
          <Card key={key}>
            <CardTitle>{t(labelKey)}</CardTitle>
            <div className="mt-3 space-y-2">
              <p className="text-2xl font-semibold text-slate-900">
                {t("ecosystem.adoption", { rate: (data.adoption_rate * 100).toFixed(1) })}
              </p>
              <p className="text-xs text-slate-400">
                {t("ecosystem.activeInactive", { active: formatNumber(data.active_n, locale), inactive: formatNumber(data.inactive_capable_n, locale) })}
              </p>
              <div className="flex justify-between text-xs">
                <span className="text-emerald-600">{t("ecosystem.riskActive", { risk: (data.mean_calibrated_risk_active * 100).toFixed(1) })}</span>
                <span className="text-slate-500">{t("ecosystem.riskInactive", { risk: (data.mean_calibrated_risk_inactive_capable * 100).toFixed(1) })}</span>
              </div>
              <p className="text-xs text-slate-400 italic">{data.observed_relationship}</p>
            </div>
          </Card>
        ) : (
          <Card key={key}>
            <CardTitle>{t(labelKey)}</CardTitle>
            <p className="mt-3 text-sm text-slate-400">{t("ecosystem.noData")}</p>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ErrorBoundary section="Segment distribution chart">
          {segmentChartData.length > 0 && (
            <div className="space-y-2">
              <ChartWrapper title={t("ecosystem.segments.title")} subtitle={t("ecosystem.segments.subtitle")} className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={segmentChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={80} />
                    <YAxis tickFormatter={(v) => formatNumber(v, locale)} />
                    <Tooltip formatter={(value) => [formatNumber(value as number, locale), t("common.subscribers")]} />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {segmentChartData.map((_d, idx) => (
                        <Cell key={idx} fill={SEGMENT_COLORS[idx % SEGMENT_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartWrapper>
              <p className="text-xs text-slate-500 leading-relaxed px-1">{t("ecosystem.segments.segmentDistributionExplain")}</p>
              <p className="text-xs text-slate-500 leading-relaxed px-1">{t("ecosystem.segments.segmentsWhy")}</p>
            </div>
          )}
        </ErrorBoundary>

        <ErrorBoundary section="Risk by segment chart">
          {highestRiskSegment && (
            <div className="space-y-2">
              <ChartWrapper title={t("ecosystem.segments.riskBySegment")} subtitle={t("ecosystem.segments.riskBySegmentSubtitle")} className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={segmentChartData.filter((d) => d.risk != null)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={80} />
                    <YAxis domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
                    <Tooltip formatter={(value) => [`${Number(value).toFixed(1)}%`, "Mean Churn Risk"]} />
                    <Bar dataKey="risk" fill="#ef4444" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartWrapper>
              <p className="text-xs text-slate-500 leading-relaxed px-1">{t("ecosystem.segments.riskBySegmentExplain")}</p>
            </div>
          )}
        </ErrorBoundary>
      </div>

      <ErrorBoundary section="Segment detail cards">
        {segmentChartData.length > 0 && (
          <section>
            <h2 className="mb-4 text-lg font-bold text-slate-800">{t("ecosystem.segments.title")}</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {segmentChartData.map((seg) => (
              <Card key={seg.name}>
                <CardTitle>{seg.name}</CardTitle>
                <div className="mt-2 space-y-1">
                  <p className="text-lg font-semibold text-slate-900">{formatNumber(seg.count, locale)}</p>
                  <p className="text-xs text-slate-400">
                    {seg.risk != null ? t("ecosystem.meanRisk", { risk: String(seg.risk) }) : t("ecosystem.noRiskData")}
                  </p>
                  <p className="text-xs italic text-slate-400">{seg.wording}</p>
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}
      </ErrorBoundary>

      {nonEcoData && nonEcoData.risk != null && (
        <Card className="border-amber-200 bg-gradient-to-br from-amber-50 to-white">
          <CardTitle>{t("ecosystem.opportunity.highRiskNonEcosystem")}</CardTitle>
          <div className="mt-3 space-y-2">
            <p className="text-xl font-semibold text-slate-900">
              {t("ecosystem.opportunity.count", { count: formatNumber(nonEcoData.count, locale), risk: nonEcoData.risk.toFixed(1) })}
            </p>
            <p className="text-sm text-slate-600">
              {t("ecosystem.opportunity.gapDescription")}
            </p>
            {highestRiskSegment && (
              <p className="text-sm font-medium text-amber-700">
                {t("ecosystem.opportunity.focusArea", { area: highestRiskSegment.name })}
              </p>
            )}
          </div>
        </Card>
      )}

      <ErrorBoundary section="Ecosystem funnel chart">
        {funnelChartData.length > 0 && (
          <ChartWrapper title={t("ecosystem.funnel.title")} subtitle={t("ecosystem.funnel.subtitle")} className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={funnelChartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis dataKey="name" type="category" width={140} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {funnelChartData.map((_d, idx) => (
                    <Cell key={idx} fill={SEGMENT_COLORS[idx % SEGMENT_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartWrapper>
        )}
      </ErrorBoundary>

      <Card className="bg-slate-50">
        <CardTitle>{t("ecosystem.methodology")}</CardTitle>
        <p className="mt-2 text-xs text-slate-500 leading-relaxed">
          {segments?.disclaimer || t("ecosystem.methodologyText")}
        </p>
      </Card>
    </div>
  );
}
