"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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
import { ExecutiveKpiCard } from "@/components/ui/executive-kpi-card";
import { SummaryBanner } from "@/components/ui/summary-banner";
import { ChartWrapper } from "@/components/ui/chart-wrapper";
import { CompatBadge } from "@/components/ui/badge";
import { Card, CardTitle } from "@/components/ui/card";
import { PageLoading } from "@/components/ui/loading";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { useI18n } from "@/i18n/provider";
import { getExecutiveRiskTier } from "@/lib/risk-labels";
import { getExecutiveRuleName } from "@/lib/rule-labels";
import { getCatalogEntry } from "@/lib/recommendation-catalog";
import { formatNumber } from "@/lib/format";
import type { KPIResponse, ChartsResponse, ModelHealth, EcosystemSummary } from "@/types/api";

const RISK_CHART_COLORS: Record<string, string> = {
  "Very High": "#ef4444",
  High: "#f59e0b",
  Medium: "#3b82f6",
  Low: "#10b981",
};

export default function DashboardPage() {
  const { t, dir, locale } = useI18n();
  const [kpis, setKpis] = useState<KPIResponse | null>(null);
  const [charts, setCharts] = useState<ChartsResponse | null>(null);
  const [health, setHealth] = useState<ModelHealth | null>(null);
  const [eco, setEco] = useState<EcosystemSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api<KPIResponse>("/dashboard/kpis").catch(() => null),
      api<ChartsResponse>("/dashboard/charts").catch(() => null),
      api<ModelHealth>("/model/health").catch(() => null),
      api<EcosystemSummary>("/ecosystem/summary").catch(() => null),
    ]).then(([k, c, h, e]) => {
      setKpis(k);
      setCharts(c);
      setHealth(h);
      setEco(e);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <PageLoading />;

  const riskChartData = (charts?.risk_distribution || []).map((d) => ({
    ...d,
    execName: getExecutiveRiskTier(d.name),
  }));

  const topRules = (charts?.rule_distribution || []).slice(0, 8);

  const highRiskCount = kpis?.high_risk_count ?? 0;
  const p1Count = kpis?.p1_action_count ?? 0;
  const totalSubs = kpis?.total_subscribers ?? 0;
  const ecoPenetration = eco
    ? ((eco.rubika_adoption?.active_n ?? 0) / Math.max(totalSubs, 1)) * 100
    : null;
  const churnRate = kpis ? kpis.actual_churn_rate * 100 : null;

  const summaryItems: { icon: string; text: string; highlight: boolean }[] = [];

  if (highRiskCount > 0) {
    summaryItems.push({
      icon: "🔴",
      text: t("dashboard.summary.criticalAttention", { count: formatNumber(highRiskCount, locale) }),
      highlight: true,
    });
  }

  if (p1Count > 0) {
    summaryItems.push({
      icon: "🟡",
      text: t("dashboard.summary.atRisk", { count: formatNumber(p1Count, locale) }),
      highlight: true,
    });
  }

  if (eco?.rubika_adoption && eco?.hamrah_man_engagement) {
    const delta = (
      (eco.hamrah_man_engagement.mean_calibrated_risk_inactive_capable -
        eco.hamrah_man_engagement.mean_calibrated_risk_active) *
      100
    ).toFixed(1);
    summaryItems.push({
      icon: "📊",
      text: t("dashboard.summary.ecosystemAdoptionAssociated", { delta: `${delta}%` }),
      highlight: false,
    });
  }

  if (kpis?.executive_summary) {
    summaryItems.push({
      icon: "💡",
      text: kpis.executive_summary,
      highlight: false,
    });
  }

  const topRule = topRules[0];
  const topCatalogEntry = topRule ? getCatalogEntry(topRule.name) : null;
  if (topCatalogEntry) {
    summaryItems.push({
      icon: "🎯",
      text: `${t("dashboard.summary.recommendedFocus", { focus: topCatalogEntry.retentionObjective })}`,
      highlight: false,
    });
  }

  const humanTouchCount = charts?.rule_distribution
    ?.filter((r) => {
      const entry = getCatalogEntry(r.name);
      return entry?.interventionType === "human-touch" || entry?.interventionType === "hybrid";
    })
    .reduce((sum, r) => sum + r.value, 0) ?? 0;

  const digitalCount = charts?.rule_distribution
    ?.filter((r) => {
      const entry = getCatalogEntry(r.name);
      return entry?.interventionType === "digital";
    })
    .reduce((sum, r) => sum + r.value, 0) ?? 0;

  const criticalPlayEntry = topRules.find((r) => {
    const entry = getCatalogEntry(r.name);
    return entry?.urgency === "immediate";
  });
  const criticalPlayCatalog = criticalPlayEntry ? getCatalogEntry(criticalPlayEntry.name) : null;

  const nonEcoRisk = eco?.ecosystem_segment_counts?.["non_ecosystem"]
    ? (eco.ecosystem_segment_counts["non_ecosystem"] / Math.max(totalSubs, 1)) * 100
    : null;

  const ecosystemGapCount = charts?.risk_distribution
    ?.filter((d) => d.name === "Very High" || d.name === "High")
    .reduce((s, d) => s + d.value, 0) ?? 0;

  return (
    <div className="space-y-6" dir={dir}>
      <header>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-900">{t("dashboard.title")}</h1>
          {health && <CompatBadge status={health.compatibility_status} />}
          {health?.artifact_freshness && (
            <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-[10px] font-medium text-slate-500 shrink-0">
              {t("dashboard.freshness.title")}: {health.champion_family}
            </span>
          )}
        </div>
        <p className="mt-1 text-slate-500">{t("app.tagline")}</p>
        <p className="mt-0.5 text-[11px] text-slate-400">{t("dashboard.freshness.label")}</p>
      </header>

      <SummaryBanner
        title={t("dashboard.summary.title")}
        items={summaryItems.length > 0 ? summaryItems : [{ icon: "⏳", text: t("dashboard.summary.noSummary"), highlight: false }]}
      />

      <section>
        <h2 className="mb-4 text-lg font-bold text-slate-800">{t("dashboard.section.businessKpis")}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <ExecutiveKpiCard
            title={t("dashboard.exec.totalSubscribers")}
            value={formatNumber(totalSubs, locale)}
            interpretation={t("dashboard.kpiWhy.totalSubscribers")}
            accentColor="indigo"
          />
          <ExecutiveKpiCard
            title={t("dashboard.exec.criticalRetention")}
            value={formatNumber(highRiskCount, locale)}
            interpretation={t("dashboard.kpiWhy.criticalRetention")}
            trend={highRiskCount > 0 ? { direction: "up", label: `${((highRiskCount / Math.max(totalSubs, 1)) * 100).toFixed(1)}${t("dashboard.highRiskTrendLabel")}` } : undefined}
            accentColor="red"
          />
          <ExecutiveKpiCard
            title={t("dashboard.exec.churnRate")}
            value={churnRate != null ? `${churnRate.toFixed(1)}%` : "—"}
            interpretation={t("dashboard.kpiWhy.churnRate")}
            accentColor="amber"
          />
          <ExecutiveKpiCard
            title={t("dashboard.exec.ecosystemPenetration")}
            value={ecoPenetration != null ? `${ecoPenetration.toFixed(1)}%` : "—"}
            interpretation={t("dashboard.kpiWhy.ecosystemPenetration")}
            accentColor="emerald"
          />
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-bold text-slate-800">{t("dashboard.section.keyRisks")}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardTitle>{t("dashboard.kpi.attention")}</CardTitle>
            <p className="mt-1 text-2xl font-bold text-slate-900">{formatNumber(highRiskCount + p1Count, locale)}</p>
            <p className="text-xs text-slate-500">{t("dashboard.kpi.attentionDetail", { critical: formatNumber(highRiskCount, locale), p1: formatNumber(p1Count, locale) })}</p>
          </Card>
          {criticalPlayCatalog && (
            <Card>
              <CardTitle>{t("dashboard.kpi.criticalPlay")}</CardTitle>
              <p className="mt-1 text-sm font-semibold text-slate-800">{criticalPlayCatalog.businessName}</p>
              <p className="mt-0.5 text-xs text-slate-500">{criticalPlayCatalog.targetSegment}</p>
              <p className="mt-1 text-[10px] text-slate-400">{t("campaigns.channelLabel")}: {criticalPlayCatalog.suggestedChannels[0]}</p>
            </Card>
          )}
          <Card>
            <CardTitle>{t("dashboard.kpi.humanIntervention")}</CardTitle>
            <p className="mt-1 text-2xl font-bold text-slate-900">{formatNumber(humanTouchCount, locale)}</p>
            <p className="text-xs text-slate-500">{t("dashboard.kpi.humanWorkload")}</p>
          </Card>
          <Card>
            <CardTitle>{t("dashboard.kpi.digitalOpportunity")}</CardTitle>
            <p className="mt-1 text-2xl font-bold text-slate-900">{formatNumber(digitalCount, locale)}</p>
            <p className="text-xs text-slate-500">{t("dashboard.kpi.digitalDesc")}</p>
          </Card>
        </div>
      </section>

      {/* ── EDA Churn Landscape ───────────────────────────────────────── */}
      <Card className="border-l-4 border-l-teal-500">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-bold text-teal-900">{t("dashboard.edaTitle")}</h2>
          <span className="rounded-full bg-teal-100 px-2 py-0.5 text-[10px] font-medium text-teal-700">6 observed rates</span>
        </div>
        <p className="mt-1 text-xs text-slate-500">{t("dashboard.edaDesc")}</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {(["i1", "i2", "i3", "i4", "i5", "i6"] as const).map((iId) => (
            <div key={iId} className="flex items-start gap-2 rounded-lg border border-teal-100 bg-teal-50/50 px-3 py-2 text-xs text-teal-800">
              <span className="mt-0.5 shrink-0 text-teal-500">▸</span>
              <span>{t(`dashboard.edaItems.${iId}`)}</span>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <ErrorBoundary section="Risk distribution chart">
          {riskChartData.length > 0 && (
            <div className="space-y-2">
              <ChartWrapper title={t("dashboard.riskDistribution")} subtitle={t("dashboard.riskDistributionSubtitle")} className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={riskChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="execName" tick={{ fontSize: 12 }} />
                    <YAxis />
                    <Tooltip
                      formatter={(value) => [formatNumber(value as number, locale), t("common.subscribers")]}
                      labelFormatter={(label) => `${t("common.riskLevel")}: ${label}`}
                    />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {riskChartData.map((entry, idx) => (
                        <Cell key={idx} fill={RISK_CHART_COLORS[entry.name] || "#4f46e5"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartWrapper>
              <p className="text-xs text-slate-500 leading-relaxed px-1">{t("dashboard.riskDistributionExplain")}</p>
              <p className="text-[10px] text-slate-400 leading-relaxed px-1 italic">{t("dashboard.riskDistributionTakeaway")}</p>
            </div>
          )}
        </ErrorBoundary>

        <ErrorBoundary section="Top retention plays chart">
          {topRules.length > 0 && (
            <div className="space-y-2">
              <ChartWrapper title={t("dashboard.topRules")} subtitle={t("dashboard.topRulesSubtitle")} className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={topRules} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis
                      dataKey="name"
                      type="category"
                      width={140}
                      tick={{ fontSize: 10 }}
                      tickFormatter={(val: string) => getExecutiveRuleName(val)}
                    />
                    <Tooltip
                      formatter={(value) => [formatNumber(value as number, locale), t("common.subscribers")]}
                      labelFormatter={(label) => getExecutiveRuleName(label)}
                    />
                    <Bar dataKey="value" fill="#0ea5e9" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartWrapper>
              <p className="text-xs text-slate-500 leading-relaxed px-1">{t("dashboard.topRulesExplain")}</p>
              <p className="text-[10px] text-slate-400 leading-relaxed px-1 italic">{t("dashboard.topRulesTakeaway")}</p>
            </div>
          )}
        </ErrorBoundary>
      </div>

      <ErrorBoundary section="Urgent opportunities">
        <section>
          <h2 className="mb-4 text-lg font-bold text-slate-800">{t("dashboard.section.urgentOpportunities")}</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {topRules.slice(0, 6).map((rule) => {
              const entry = getCatalogEntry(rule.name);
              if (!entry) return null;
              return (
                <Card key={rule.name}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-800 truncate">{entry.businessName}</p>
                      <p className="mt-1 text-2xl font-bold text-slate-900">{formatNumber(rule.value, locale)}</p>
                      <p className="text-xs text-slate-500 leading-snug mt-1">{entry.retentionObjective}</p>
                    </div>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                      entry.urgency === "immediate" ? "bg-red-50 text-red-600" :
                      entry.urgency === "short-term" ? "bg-amber-50 text-amber-600" :
                      "bg-blue-50 text-blue-600"
                    }`}>
                      {entry.urgency}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">
                      {entry.interventionType}
                    </span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">
                      {entry.suggestedChannels[0]}
                    </span>
                  </div>
                  {entry.playbookOffers.length > 0 && (
                    <p className="mt-1.5 text-[10px] text-slate-400 truncate">
                      Offer: {entry.playbookOffers[0].title}
                    </p>
                  )}
                </Card>
              );
            })}
          </div>
        </section>
      </ErrorBoundary>

      <div className="grid gap-6 lg:grid-cols-2">
        <ErrorBoundary section="Operational focus">
          <section>
            <h2 className="mb-4 text-lg font-bold text-slate-800">{t("dashboard.section.operationalFocus")}</h2>
            <div className="space-y-3">
              {humanTouchCount > 0 && (
                <Card className="border-amber-200 bg-gradient-to-br from-amber-50 to-white">
                  <CardTitle>{t("dashboard.kpi.humanIntervention")}</CardTitle>
                  <p className="mt-1 text-2xl font-bold text-slate-900">{formatNumber(humanTouchCount, locale)}</p>
                  <p className="text-xs text-slate-500">{t("dashboard.kpi.humanWorkload")}</p>
                </Card>
              )}
              {digitalCount > 0 && (
                <Card className="border-indigo-200 bg-gradient-to-br from-indigo-50 to-white">
                  <CardTitle>{t("dashboard.kpi.digitalOpportunity")}</CardTitle>
                  <p className="mt-1 text-2xl font-bold text-slate-900">{formatNumber(digitalCount, locale)}</p>
                  <p className="text-xs text-slate-500">{t("dashboard.kpi.digitalDesc")}</p>
                </Card>
              )}
              {eco && (
                <Card className="border-emerald-200 bg-gradient-to-br from-emerald-50 to-white">
                  <CardTitle>{t("ecosystem.title")}</CardTitle>
                  <p className="mt-1 text-sm text-slate-700">
                    {t("dashboard.summary.ecosystemAdoptionAssociated", { delta: `${nonEcoRisk?.toFixed(0) ?? "?"}%` })}
                  </p>
                  {ecosystemGapCount > 0 && (
                    <p className="mt-1 text-xs text-slate-500">
                      {t("dashboard.kpi.highRiskOutside", { count: formatNumber(ecosystemGapCount, locale) })}
                    </p>
                  )}
                </Card>
              )}
            </div>
          </section>
        </ErrorBoundary>

        <ErrorBoundary section="Revenue protection">
          <section>
            <h2 className="mb-4 text-lg font-bold text-slate-800">{t("dashboard.section.revenueProtection")}</h2>
          <div className="space-y-3">
            {topCatalogEntry && (
              <Card className="border-red-200 bg-gradient-to-br from-red-50 to-white">
                <CardTitle>{t("dashboard.kpi.topPlayDetail")}</CardTitle>
                <p className="mt-1 text-sm font-semibold text-slate-800">{topCatalogEntry.businessName}</p>
                <p className="mt-1 text-xs text-slate-600 leading-relaxed">{topCatalogEntry.executiveSummary}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {topCatalogEntry.suggestedChannels.map((ch) => (
                    <span key={ch} className="rounded-md border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-600">
                      {ch}
                    </span>
                  ))}
                </div>
                {topCatalogEntry.playbookOffers.length > 0 && (
                  <div className="mt-2 rounded bg-white/50 p-2">
                    <p className="text-[10px] font-medium text-slate-500">{t("campaigns.recommendedOffer")}</p>
                    <p className="text-xs text-slate-700">{topCatalogEntry.playbookOffers[0].title}</p>
                    <p className="text-[10px] text-slate-400">{topCatalogEntry.playbookOffers[0].description}</p>
                  </div>
                )}
                <p className="mt-2 text-[10px] text-slate-400">{t("campaigns.successSignal", { signal: topCatalogEntry.successSignal })}</p>
              </Card>
            )}
            <Card>
              <CardTitle>{t("dashboard.kpi.topRiskDrivers")}</CardTitle>
              <div className="mt-2 space-y-1 text-xs text-slate-600">
                <p>{t("dashboard.kpi.riskDescription")}</p>
                <p>{t("dashboard.kpi.focusSaveDesc", { count: formatNumber(highRiskCount, locale) })}</p>
                {p1Count > 0 && <p>{t("dashboard.kpi.prioritySaveDesc", { count: formatNumber(p1Count, locale) })}</p>}
              </div>
            </Card>
          </div>
        </section>
        </ErrorBoundary>
      </div>

      <ErrorBoundary section="Operational workload KPIs">
        {(kpis || health || eco) && (
          <section>
            <h2 className="mb-4 text-lg font-bold text-slate-800">{t("dashboard.section.operationalWorkload")}</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <ExecutiveKpiCard
              title={t("dashboard.exec.prioritySaves")}
              value={formatNumber(p1Count, locale)}
              interpretation={t("dashboard.kpiWhy.prioritySaves")}
              trend={p1Count > 0 ? { direction: "up", label: t("dashboard.kpi.needsAttention") } : undefined}
              accentColor="amber"
            />
            <ExecutiveKpiCard
              title={t("dashboard.exec.revenueExposure")}
              value={highRiskCount > 0 ? `${formatNumber(highRiskCount * 150000, locale)} T` : "—"}
              interpretation={t("dashboard.kpiWhy.revenueExposure")}
              accentColor="red"
            />
            <ExecutiveKpiCard
              title={t("dashboard.exec.campaignCoverage")}
              value={topRules.length.toString()}
              interpretation={t("dashboard.kpiWhy.campaignCoverage")}
              accentColor="blue"
            />
            {health && (
              <ExecutiveKpiCard
                title={t("dashboard.prAuc")}
                value={health.pr_auc?.toFixed(3) ?? "—"}
                interpretation={`${t("health.championFamily")}: ${health.champion_family} — ${t("health.calibration")}: ${health.calibration_method}`}
                accentColor="slate"
              />
            )}
          </div>
        </section>
      )}
      </ErrorBoundary>

      <section>
        <h2 className="mb-4 text-lg font-bold text-slate-800">{t("dashboard.section.actionItems")}</h2>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/queue"
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-indigo-500"
          >
            {t("dashboard.actionItems.openQueue")}
          </Link>
          <Link
            href="/campaigns"
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
          >
            {t("dashboard.actionItems.viewCampaigns")}
          </Link>
          <Link
            href="/ecosystem"
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
          >
            {t("dashboard.actionItems.viewEcosystem")}
          </Link>
          <Link
            href="/health"
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
          >
            {t("dashboard.actionItems.viewHealth")}
          </Link>
        </div>
      </section>
    </div>
  );
}
