"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "@/lib/api";
import { Card, CardTitle } from "@/components/ui/card";
import { KpiCard } from "@/components/ui/kpi-card";
import { ExecutiveRiskBadge, PriorityBadge, CompatBadge } from "@/components/ui/badge";
import { NarrativeCard } from "@/components/ui/narrative-card";
import { TechnicalDrawer } from "@/components/ui/technical-drawer";
import { SummaryBanner } from "@/components/ui/summary-banner";
import { PageLoading } from "@/components/ui/loading";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { useI18n } from "@/i18n/provider";
import {
  getExecutiveEcosystemSegment,
  getExecutiveDriver,
  getCostTierLabel,
  getCrmQueueLabel,
  getDriverSourceLabel,
  getInterventionTypeLabel,
  getRetentionStrategyLabel,
  getEngagementLevelLabel,
} from "@/lib/label-resolver";
import { buildRecommendationNarrative } from "@/lib/recommendation-narrative";
import { getCatalogEntry } from "@/lib/recommendation-catalog";
import { formatNumber, formatPercent } from "@/lib/format";
import type { SubscriberProfile, ShapDriver } from "@/types/api";

type Tab = "overview" | "shap" | "campaign" | "governance";

export default function SubscriberPage() {
  const { t, dir, locale } = useI18n();
  const params = useParams();
  const id = params.id as string;
  const [profile, setProfile] = useState<SubscriberProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("overview");
  const fr = t("common.unknown");

  useEffect(() => {
    setLoading(true);
    api<SubscriberProfile>(`/subscribers/${id}`)
      .then(setProfile)
      .catch(() => setProfile(null))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <PageLoading />;
  if (!profile) return (
    <div className="flex items-center justify-center py-20" dir={dir}>
      <div className="text-center">
        <p className="text-lg font-medium text-slate-600">{t("subscriber.notFound")}</p>
        <Link href="/queue" className="mt-2 inline-block text-sm text-indigo-600 hover:underline">
          {t("subscriber.backToQueue")}
        </Link>
      </div>
    </div>
  );

  const { score, recommendation, ecosystem_profile, shap_explanations, recommendation_rationale, campaign_metadata, governance_metadata } = profile;
  const p = profile.profile;

  const narrative = buildRecommendationNarrative(
    recommendation_rationale?.rule_id,
    recommendation?.recommended_action,
  );

  const catalogEntry = getCatalogEntry(recommendation_rationale?.rule_id);

  const TABS: { key: Tab; labelKey: string }[] = [
    { key: "overview", labelKey: "subscriber.tabs.overview" },
    { key: "shap", labelKey: "subscriber.tabs.shap" },
    { key: "campaign", labelKey: "subscriber.tabs.campaign" },
    { key: "governance", labelKey: "subscriber.tabs.governance" },
  ];

  const shapChartData = [...(shap_explanations?.positive_drivers || [])]
    .sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value))
    .slice(0, 10)
    .map((d) => ({
      name: d.business_label.split(" ")[0],
      impact: d.shap_value,
      narrative: d.narrative,
    }));

  const summaryItems = [];
  if (score.churn_probability != null) {
    const riskPct = (score.churn_probability * 100).toFixed(1);
    summaryItems.push({
      icon: score.churn_probability > 0.5 ? "🔴" : score.churn_probability > 0.3 ? "🟡" : "🟢",
      text: `${t("subscriber.summary.calibratedRisk")}: ${riskPct}%`,
      highlight: score.churn_probability > 0.5,
    });
  }
  if (narrative.businessName) {
    summaryItems.push({
      icon: "🎯",
      text: `${t("subscriber.summary.play")}: ${narrative.businessName}`,
      highlight: false,
    });
  }
  if (ecosystem_profile?.ecosystem_segment) {
    summaryItems.push({
      icon: "📊",
      text: `${t("subscriber.segment")}: ${getExecutiveEcosystemSegment(ecosystem_profile.ecosystem_segment)}`,
      highlight: false,
    });
  }
  if (recommendation?.campaign_queue_rank != null) {
    summaryItems.push({
      icon: "📋",
      text: `${t("subscriber.summary.queueRank")}: #${recommendation.campaign_queue_rank}`,
      highlight: false,
    });
  }
  if (catalogEntry?.retentionObjective) {
    summaryItems.push({
      icon: "💡",
      text: catalogEntry.retentionObjective,
      highlight: false,
    });
  }

  return (
    <div className="space-y-6" dir={dir}>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900">
              {t("subscriber.title", { id: profile.subscriber_id })}
            </h1>
            <ExecutiveRiskBadge tier={score.risk_tier} showTechnical />
            <CompatBadge status={governance_metadata?.compatibility_status} />
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {p.gender && `${p.gender}, `}{p.age != null ? `${p.age}y, ` : ""}
            {p.sim_card_type && `${p.sim_card_type}, `}
            {p.mobile_data_generation || ""}
            {p.sim_tenure_months != null ? ` — ${p.sim_tenure_months}m tenure` : ""}
            {p.monthly_spend_toman != null ? ` — ${formatNumber(p.monthly_spend_toman, locale)} T/mo` : ""}
          </p>
        </div>
        <Link
          href="/queue"
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-600 transition-colors hover:bg-slate-50"
        >
          {t("subscriber.backToQueue")}
        </Link>
      </header>

      <SummaryBanner
        title={`${t("profile.customerIntelligence")} — ${t("subscriber.title", { id: profile.subscriber_id })}`}
        items={summaryItems.length > 0 ? summaryItems : [{ icon: "⏳", text: t("subscriber.summary.loading"), highlight: false }]}
      />

      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-1">
        {TABS.map(({ key, labelKey }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded-t-lg px-4 py-2 text-sm font-medium transition-colors ${
              tab === key
                ? "border-b-2 border-indigo-600 text-indigo-600"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t(labelKey)}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <ErrorBoundary section="Subscriber overview">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              title={t("subscriber.calibratedRisk")}
              value={formatPercent(score.churn_probability, locale)}
              subtitle={t("subscriber.calibratedRiskWhy")}
            />
            <KpiCard
              title={t("subscriber.rawScore")}
              value={formatPercent(score.churn_probability_raw, locale)}
              subtitle={t("subscriber.rawScoreWhy")}
            />
            <Card>
              <CardTitle>{t("subscriber.riskBand")}</CardTitle>
              <p className="mt-2 text-xl font-semibold text-slate-900">
                <ExecutiveRiskBadge tier={score.risk_tier} showTechnical />
              </p>
              <p className="mt-1 text-xs text-slate-400">
                {t("subscriber.intervention", { type: getInterventionTypeLabel(recommendation?.intervention_type) })}
              </p>
            </Card>
            <Card>
              <CardTitle>{t("subscriber.actualChurn")}</CardTitle>
              <p className="mt-2 text-xl font-semibold text-slate-900">{p.churn_actual ? t("common.yes") : t("common.no")}</p>
              <p className="text-xs text-slate-400">{t("subscriber.snapshotLabel")}</p>
            </Card>
          </div>

          <NarrativeCard narrative={narrative} />

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardTitle>{t("profile.whyThisCustomer")}</CardTitle>
              <p className="mt-2 text-xs text-slate-500 leading-relaxed">{t("profile.whyThisCustomerDesc")}</p>
              <p className="mt-2 text-sm leading-relaxed text-slate-700">
                {narrative.executiveSummary}
              </p>
              <div className="mt-3 space-y-1 text-xs text-slate-500">
                <p><span className="font-medium text-slate-600">{t("subscriber.segment")}:</span> {getExecutiveEcosystemSegment(ecosystem_profile?.ecosystem_segment)}</p>
                <p><span className="font-medium text-slate-600">{t("profile.primaryDriver")}:</span> {getExecutiveDriver(recommendation_rationale?.final_top_driver)}</p>
                <p><span className="font-medium text-slate-600">{t("profile.driverSource")}:</span> {getDriverSourceLabel(recommendation_rationale?.final_top_driver_source)}</p>
              </div>
            </Card>
            <Card>
              <CardTitle>{t("profile.whyThisPlayFits")}</CardTitle>
              <p className="mt-2 text-xs text-slate-500 leading-relaxed">{t("profile.whyThisPlayFitsDesc")}</p>
              <p className="mt-2 text-sm leading-relaxed text-slate-700">
                {narrative.targetSegment}. {narrative.retentionObjective}
              </p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                  catalogEntry?.urgency === "immediate" ? "bg-red-50 text-red-700" :
                  catalogEntry?.urgency === "short-term" ? "bg-amber-50 text-amber-700" :
                  "bg-blue-50 text-blue-700"
                }`}>
                  {narrative.urgencyLabel}
                </span>
                <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-medium text-blue-700">
                  {narrative.interventionLabel}
                </span>
                {catalogEntry?.estimatedComplexity && (
                  <span className="rounded-full bg-purple-50 px-2.5 py-1 text-[11px] font-medium text-purple-700">
                    {catalogEntry.estimatedComplexity}
                  </span>
                )}
              </div>
              {narrative.suggestedChannels.length > 0 && (
                <div className="mt-2">
                  <span className="text-xs font-medium text-slate-500">{t("profile.preferredChannel")}:</span>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {narrative.suggestedChannels.map((ch) => (
                      <span key={ch} className="rounded-md border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-600">
                        {ch}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {catalogEntry?.successSignal && (
                <p className="mt-2 text-xs text-emerald-600">{t("campaigns.successSignal", { signal: catalogEntry.successSignal })}</p>
              )}
              <p className="mt-2 text-xs text-slate-500 leading-relaxed">
                {narrative.operationalGuidance}
              </p>
            </Card>
          </div>

          <Card>
            <CardTitle>{t("subscriber.ecosystemProfile")}</CardTitle>
            <div className="mt-3 grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
              {[
                { label: t("ecosystem.rubika"), value: ecosystem_profile?.has_rubika },
                { label: t("ecosystem.ewano"), value: ecosystem_profile?.has_ewano },
                { label: t("ecosystem.hamrahMan"), value: ecosystem_profile?.has_hamrahman },
                { label: t("ecosystem.volte"), value: ecosystem_profile?.has_volte },
              ].map((item) => (
                <div key={item.label}>
                  <span className="text-slate-400">{item.label}</span>
                  <p className={`font-medium ${item.value ? "text-emerald-600" : "text-slate-500"}`}>
                    {item.value ? t("common.yes") : t("common.no")}
                  </p>
                </div>
              ))}
              <div>
                <span className="text-slate-400">{t("subscriber.segment")}</span>
                <p className="font-medium text-slate-900">{getExecutiveEcosystemSegment(ecosystem_profile?.ecosystem_segment)}</p>
              </div>
              <div>
                <span className="text-slate-400">{t("subscriber.products")}</span>
                <p className="font-medium text-slate-900">{ecosystem_profile?.ecosystem_product_count ?? fr}</p>
              </div>
              <div>
                <span className="text-slate-400">{t("profile.engagementLevel")}</span>
                <p className="font-medium text-slate-900">{getEngagementLevelLabel(ecosystem_profile?.ecosystem_engagement_level)}</p>
              </div>
              <div>
                <span className="text-slate-400">{t("profile.retentionStrategy")}</span>
                <p className="font-medium text-slate-900">{getRetentionStrategyLabel(ecosystem_profile?.ecosystem_retention_strategy)}</p>
              </div>
            </div>
          </Card>

          <TechnicalDrawer
            title="Raw Technical Codes"
            items={[
              { label: "Rule ID", value: recommendation_rationale?.rule_id, mono: true },
              { label: "Risk Tier (raw)", value: score.risk_tier, mono: true },
              { label: "Campaign Priority", value: campaign_metadata?.campaign_priority, mono: true },
              { label: "Cost Tier", value: getCostTierLabel(campaign_metadata?.campaign_cost_tier) },
              { label: "Cost Tier (raw)", value: campaign_metadata?.campaign_cost_tier, mono: true },
              { label: "CRM Queue", value: getCrmQueueLabel(campaign_metadata?.crm_queue) },
              { label: "CRM Queue (raw)", value: campaign_metadata?.crm_queue, mono: true },
              { label: "Driver Source (raw)", value: recommendation_rationale?.final_top_driver_source, mono: true },
              { label: "Intervention Type (raw)", value: recommendation?.intervention_type, mono: true },
              { label: "Retention Strategy (raw)", value: ecosystem_profile?.ecosystem_retention_strategy, mono: true },
              { label: "Engagement Level (raw)", value: ecosystem_profile?.ecosystem_engagement_level, mono: true },
              { label: "Digital Only", value: campaign_metadata?.digital_only_flag ? "Yes" : "No" },
              { label: "Escalation Required", value: campaign_metadata?.escalation_required ? "Yes" : "No" },
              { label: "Human Touch", value: campaign_metadata?.human_touch_flag ? "Yes" : "No" },
              { label: "Raw Score", value: score.churn_probability_raw != null ? `${(score.churn_probability_raw * 100).toFixed(2)}%` : "—" },
              { label: "Schema Version", value: governance_metadata?.schema_version, mono: true },
              { label: t("subscriber.governance.championFamily"), value: governance_metadata?.champion_family, mono: true },
            ]}
          />
        </ErrorBoundary>
      )}

      {tab === "shap" && (
        <ErrorBoundary section="SHAP explanations">
          <div className="space-y-6">
            <Card>
              <CardTitle>{t("subscriber.shap.narrative")}</CardTitle>
              <p className="mt-2 text-sm text-slate-600">{shap_explanations?.narrative || t("subscriber.shap.narrativePlaceholder")}</p>
              <p className="mt-2 text-xs text-slate-400 italic">
                {t("subscriber.shap.narrativeDisclaimer")}
              </p>
            </Card>

            {shap_explanations?.positive_drivers && shap_explanations.positive_drivers.length > 0 && (
              <Card>
                <CardTitle>{t("subscriber.shap.riskIncreasing")}</CardTitle>
                <div className="mt-4 h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={shapChartData} layout="vertical">
                      <XAxis type="number" />
                      <YAxis dataKey="name" type="category" width={100} tick={{ fontSize: 11 }} />
                      <Tooltip formatter={(value) => [Number(value).toFixed(4), t("subscriber.shap.shapImpact")]} />
                      <Bar dataKey="impact" fill="#ef4444" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              {shap_explanations?.positive_drivers && shap_explanations.positive_drivers.length > 0 && (
                <Card>
                  <CardTitle>{t("subscriber.shap.topUpDrivers")}</CardTitle>
                  <ul className="mt-3 space-y-2">
                    {shap_explanations.positive_drivers.slice(0, 5).map((d: ShapDriver, i: number) => (
                      <li key={i} className="border-l-2 border-red-400 pl-3 text-sm rtl:border-l-0 rtl:border-r-2 rtl:pl-0 rtl:pr-3">
                        <span className="font-medium text-slate-800">{d.business_label}</span>
                        <p className="text-xs text-slate-500">{d.narrative}</p>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
              {shap_explanations?.negative_drivers && shap_explanations.negative_drivers.length > 0 && (
                <Card>
                  <CardTitle>{t("subscriber.shap.topDownDrivers")}</CardTitle>
                  <ul className="mt-3 space-y-2">
                    {shap_explanations.negative_drivers.slice(0, 5).map((d: ShapDriver, i: number) => (
                      <li key={i} className="border-l-2 border-emerald-400 pl-3 text-sm rtl:border-l-0 rtl:border-r-2 rtl:pl-0 rtl:pr-3">
                        <span className="font-medium text-slate-800">{d.business_label}</span>
                        <p className="text-xs text-slate-500">{d.narrative}</p>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
            </div>

            {shap_explanations?.shap_risk_up_drivers && (
              <Card>
                <CardTitle>{t("subscriber.shap.riskSummary")}</CardTitle>
                <div className="mt-2 grid gap-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-500">{t("subscriber.shap.primaryDriver")}</span>
                    <span className="font-medium">{shap_explanations.shap_top_driver || fr}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">{t("subscriber.shap.riskUp")}</span>
                    <span className="font-medium">{shap_explanations.shap_risk_up_drivers || fr}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">{t("subscriber.shap.riskDown")}</span>
                    <span className="font-medium">{shap_explanations.shap_risk_down_drivers || fr}</span>
                  </div>
                </div>
              </Card>
            )}
          </div>
        </ErrorBoundary>
      )}

      {tab === "campaign" && (
        <ErrorBoundary section="Campaign metadata">
          <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardTitle>{t("subscriber.campaign.assignment")}</CardTitle>
            <div className="mt-3 space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">{t("subscriber.campaign.priority")}</span>
                <PriorityBadge priority={campaign_metadata?.campaign_priority} />
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">{t("profile.costTier")}</span>
                <span className="font-medium">{getCostTierLabel(campaign_metadata?.campaign_cost_tier)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">{t("profile.crmQueue")}</span>
                <span className="font-medium">{getCrmQueueLabel(campaign_metadata?.crm_queue)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">{t("subscriber.campaign.queueRank")}</span>
                <span className="font-medium">{recommendation?.campaign_queue_rank ?? fr}</span>
              </div>
            </div>
          </Card>
          <Card>
            <CardTitle>{t("subscriber.campaign.channelConfig")}</CardTitle>
            <div className="mt-3 space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">{t("subscriber.campaign.primary")}</span>
                <span className="font-medium">{campaign_metadata?.primary_channel || fr}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">{t("subscriber.campaign.secondary")}</span>
                <span className="font-medium">{campaign_metadata?.secondary_channel || fr}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">{t("subscriber.campaign.channelGroup")}</span>
                <span className="font-medium">{campaign_metadata?.campaign_channel_group || fr}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">{t("subscriber.campaign.urgency")}</span>
                <span className="font-medium">{campaign_metadata?.campaign_urgency_days != null ? t("subscriber.campaign.urgencyDays", { days: campaign_metadata.campaign_urgency_days }) : fr}</span>
              </div>
            </div>
          </Card>
          <Card>
            <CardTitle>{t("subscriber.campaign.flags")}</CardTitle>
            <div className="mt-3 space-y-2 text-sm">
              {[
                { label: t("subscriber.campaign.digitalOnly"), value: campaign_metadata?.digital_only_flag },
                { label: t("subscriber.campaign.escalation"), value: campaign_metadata?.escalation_required },
                { label: t("subscriber.campaign.humanTouch"), value: campaign_metadata?.human_touch_flag },
              ].map((f) => (
                <div key={f.label} className="flex items-center gap-2">
                  <div className={`h-2.5 w-2.5 shrink-0 rounded-full ${f.value ? "bg-emerald-500" : "bg-slate-300"}`} />
                  <span className="text-slate-600">{f.label}</span>
                  <span className={dir === "rtl" ? "mr-auto text-slate-400" : "ml-auto text-slate-400"}>{f.value ? t("common.yes") : t("common.no")}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
        </ErrorBoundary>
      )}

      {tab === "governance" && (
        <ErrorBoundary section="Subscriber governance">
          <Card>
          <CardTitle>{t("subscriber.governance.title")}</CardTitle>
          <p className="mt-1 text-xs text-slate-400 leading-relaxed">{t("subscriber.governance.subtitle")}</p>
          <div className="mt-4 space-y-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[
                { label: t("subscriber.governance.schema"), value: governance_metadata?.schema_version },
                { label: t("subscriber.governance.bundle"), value: governance_metadata?.bundle_schema_version },
                { label: t("subscriber.governance.featureContract"), value: governance_metadata?.feature_contract_version },
                { label: t("subscriber.governance.recommendationSchema"), value: governance_metadata?.recommendation_schema_version },
                { label: t("subscriber.governance.shapSchema"), value: governance_metadata?.shap_schema_version },
                { label: t("subscriber.governance.championFamily"), value: governance_metadata?.champion_family },
              ].map((item) => (
                <div key={item.label} className="rounded-lg bg-slate-50 p-3">
                  <p className="text-xs text-slate-400">{item.label}</p>
                  <p className="mt-1 font-mono text-sm font-medium text-slate-800">{item.value || fr}</p>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-slate-500">{t("subscriber.governance.compatibility")}:</span>
              <CompatBadge status={governance_metadata?.compatibility_status} />
            </div>
          </div>
        </Card>
        </ErrorBoundary>
      )}
    </div>
  );
}
