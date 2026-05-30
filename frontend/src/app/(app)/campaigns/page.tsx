"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";
import { api } from "@/lib/api";
import { Card, CardTitle } from "@/components/ui/card";
import { ChartWrapper } from "@/components/ui/chart-wrapper";
import { PageLoading } from "@/components/ui/loading";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { RuleLabel } from "@/components/ui/rule-label";
import { useI18n } from "@/i18n/provider";
import { getExecutiveRuleName } from "@/lib/rule-labels";
import { getCatalogEntry } from "@/lib/recommendation-catalog";
import { buildRecommendationNarrative } from "@/lib/recommendation-narrative";
import { formatNumber } from "@/lib/format";
import type { ChartsResponse } from "@/types/api";

const COLORS = ["#4f46e5", "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#6366f1"];

type ReadinessLevel = "ready" | "needs-attention" | "monitor";

function getReadinessLevel(entry: ReturnType<typeof getCatalogEntry>, t: (key: string) => string): { level: ReadinessLevel; label: string; color: string } {
  if (!entry) return { level: "monitor", label: t("campaigns.readinessUnknown"), color: "bg-slate-100 text-slate-500" };
  if (entry.urgency === "immediate") return { level: "needs-attention", label: t("campaigns.readinessNeedsAttention"), color: "bg-red-50 text-red-700" };
  if (entry.urgency === "short-term") return { level: "ready", label: t("campaigns.readinessReady"), color: "bg-emerald-50 text-emerald-700" };
  return { level: "monitor", label: t("campaigns.readinessMonitor"), color: "bg-blue-50 text-blue-700" };
}

export default function CampaignsPage() {
  const { t, dir, locale } = useI18n();
  const [charts, setCharts] = useState<ChartsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedRule, setSelectedRule] = useState<string | null>(null);

  useEffect(() => {
    api<ChartsResponse>("/dashboard/charts")
      .then(setCharts)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <PageLoading />;
  if (!charts) return <p className="text-red-500">{t("common.error")}</p>;

  const rules = charts.rule_distribution;
  const selectedNarrative = selectedRule ? buildRecommendationNarrative(selectedRule, null) : null;

  return (
    <div className="space-y-6" dir={dir}>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">{t("campaigns.title")}</h1>
        <p className="mt-1 text-sm text-slate-500">{t("campaigns.description")}</p>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <ErrorBoundary section="Campaign rules volume chart">
          {rules.length > 0 && (
            <div className="space-y-2">
              <ChartWrapper title={t("campaigns.rulesVolume")} subtitle={t("campaigns.rulesVolumeSubtitle")} className="h-96">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rules}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 8 }}
                      angle={-30}
                      textAnchor="end"
                      height={100}
                      tickFormatter={(val: string) => getExecutiveRuleName(val)}
                    />
                    <YAxis />
                    <Tooltip
                      formatter={(value) => [formatNumber(value as number, locale), "Subscribers"]}
                      labelFormatter={(label) => getExecutiveRuleName(label)}
                    />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {rules.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartWrapper>
              <p className="text-xs text-slate-500 leading-relaxed px-1">{t("campaigns.rulesVolumeExplain")}</p>
            </div>
          )}
        </ErrorBoundary>

        <ErrorBoundary section="Campaign priority mix chart">
          {charts.campaign_priority_distribution && charts.campaign_priority_distribution.length > 0 && (
            <div className="space-y-2">
              <ChartWrapper title={t("campaigns.priorityMix")} subtitle={t("campaigns.priorityMixSubtitle")} className="h-96">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={charts.campaign_priority_distribution}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="value" fill="#14b8a6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartWrapper>
              <p className="text-xs text-slate-500 leading-relaxed px-1">{t("campaigns.priorityMixExplain")}</p>
            </div>
          )}
        </ErrorBoundary>
      </div>

      <ErrorBoundary section="Campaign summary cards">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardTitle>{t("campaigns.totalRules")}</CardTitle>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{rules.length}</p>
          </Card>
          <Card>
            <CardTitle>{t("campaigns.topRule")}</CardTitle>
            <div className="mt-2">
              <RuleLabel ruleId={rules[0]?.name || null} />
            </div>
            <p className="mt-1 text-xs text-slate-400">
              {t("campaigns.subscribers", { count: formatNumber(rules[0]?.value ?? 0, locale) })}
            </p>
            {selectedNarrative && (
              <p className="mt-1 text-xs italic text-slate-500 leading-relaxed">{selectedNarrative.ruleDescription}</p>
            )}
          </Card>
          <Card>
            <CardTitle>{t("campaigns.highestPriority")}</CardTitle>
            <p className="mt-2 text-sm font-medium text-slate-900">
              {charts.campaign_priority_distribution[0]?.name || "—"}
            </p>
            <p className="text-xs text-slate-400">
              {t("campaigns.subscribers", { count: formatNumber(charts.campaign_priority_distribution[0]?.value ?? 0, locale) })}
            </p>
          </Card>
          <Card>
            <CardTitle>{t("campaigns.prioritiesUsed")}</CardTitle>
            <p className="mt-2 text-2xl font-semibold text-slate-900">
              {charts.campaign_priority_distribution.length}
            </p>
          </Card>
        </div>
      </ErrorBoundary>

      <ErrorBoundary section="Campaign playbook">
        {rules.length > 0 && (
          <section>
            <h2 className="mb-4 text-lg font-bold text-slate-800">
              {t("campaigns.playbookTitle")}
            </h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {rules.map((rule) => {
              const narrative = buildRecommendationNarrative(rule.name, null);
              const entry = getCatalogEntry(rule.name);
              const readiness = getReadinessLevel(entry, t);
              const isSelected = selectedRule === rule.name;
              return (
                <div
                  key={rule.name}
                  className={`cursor-pointer transition-shadow hover:shadow-md ${isSelected ? "ring-2 ring-indigo-400" : ""}`}
                  onClick={() => setSelectedRule(isSelected ? null : rule.name)}
                >
                  <Card>
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-800">{narrative.businessName}</p>
                      <span className="shrink-0 rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-600">
                        {formatNumber(rule.value, locale)}
                      </span>
                    </div>

                    <p className="mt-2 text-xs text-slate-500 leading-relaxed">
                      {narrative.retentionObjective}
                    </p>

                    <div className="mt-3 flex flex-wrap gap-1">
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${readiness.color}`}>
                        {readiness.label}
                      </span>
                      <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] text-blue-700">
                        {narrative.interventionLabel.split("—")[0].trim()}
                      </span>
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">
                        {narrative.estimatedComplexityLabel.split("—")[0].trim()}
                      </span>
                    </div>

                    <div className="mt-2 flex items-center gap-2 text-[10px] text-slate-400">
                      <span>{t("campaigns.targetSegment")}: {narrative.targetSegment}</span>
                      {entry?.successSignal && (
                        <span className="text-emerald-600">✓ {entry.successSignal}</span>
                      )}
                    </div>

                    {narrative.suggestedChannels.length > 0 && (
                      <p className="mt-1 text-[10px] text-slate-400">
                        {t("campaigns.channels")}: {narrative.suggestedChannels.join(", ")}
                      </p>
                    )}

                    {entry?.playbookOffers?.[0] && !isSelected && (
                      <p className="mt-1.5 text-[10px] text-slate-400 truncate">
                        {t("campaigns.expectedOutcome")}: {entry.playbookOffers[0].title}
                      </p>
                    )}

                    {isSelected && (
                      <div className="mt-3 space-y-2 border-t pt-3">
                        {entry?.executiveSummary && (
                          <div className="rounded bg-indigo-50 p-2">
                            <p className="text-[10px] font-medium text-indigo-700">{t("campaigns.summary")}</p>
                            <p className="mt-0.5 text-[10px] text-indigo-600">{entry.executiveSummary}</p>
                          </div>
                        )}
                        {narrative.playbookOffers.length > 0 && (
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
                              {t("campaigns.telecomOffers")}
                            </p>
                            <div className="space-y-1.5">
                              {narrative.playbookOffers.map((offer, i) => (
                                <div key={i} className="rounded bg-slate-50 p-2">
                                  <div className="flex items-start justify-between gap-1">
                                    <p className="text-xs font-medium text-slate-700">{offer.title}</p>
                                    <span className="shrink-0 rounded bg-white px-1 text-[9px] text-slate-400">{offer.channel}</span>
                                  </div>
                                  <p className="mt-0.5 text-[10px] text-slate-500">{offer.description}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        <div className="rounded bg-indigo-50 p-2">
                          <p className="text-[10px] font-medium text-indigo-700">{t("campaigns.guidance")}</p>
                          <p className="mt-0.5 text-[10px] text-indigo-600">{narrative.operationalGuidance}</p>
                        </div>
                        <div className="text-[10px] text-slate-400 font-mono">
                          {t("campaigns.technicalId")}: {narrative.technicalRuleId}
                        </div>
                      </div>
                    )}
                  </Card>
                </div>
              );
            })}
          </div>
        </section>
      )}
      </ErrorBoundary>
    </div>
  );
}
