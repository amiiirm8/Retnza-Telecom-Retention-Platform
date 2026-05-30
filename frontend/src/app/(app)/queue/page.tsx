"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api, apiBlob } from "@/lib/api";
import { DataTable } from "@/components/ui/table";
import { Pagination } from "@/components/ui/pagination";
import { Select } from "@/components/ui/select";
import { ExecutiveRiskBadge, PriorityBadge } from "@/components/ui/badge";
import { RuleLabel } from "@/components/ui/rule-label";
import { PageLoading } from "@/components/ui/loading";
import { Card, CardTitle } from "@/components/ui/card";
import { NarrativeCard } from "@/components/ui/narrative-card";
import { TechnicalDrawer } from "@/components/ui/technical-drawer";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { useI18n } from "@/i18n/provider";
import {
  getExecutiveEcosystemSegment,
  getExecutiveDriver,
  getCostTierLabel,
  getCrmQueueLabel,
  getInterventionTypeLabel,
  getRetentionStrategyLabel,
} from "@/lib/label-resolver";
import { buildRecommendationNarrative } from "@/lib/recommendation-narrative";
import { getCatalogEntry } from "@/lib/recommendation-catalog";
import { formatNumber, formatPercent } from "@/lib/format";
import type { RecommendationListResponse, RecommendationItem } from "@/types/api";

type SortField = "campaign_queue_rank" | "churn_probability" | "churn_probability_raw" | "campaign_priority" | "risk_tier" | "ecosystem_segment";
type SortDir = "asc" | "desc";
type QueueTab = "all" | "high-risk" | "p1" | "digital-only" | "human-touch";

const RISK_TIERS = ["", "Very High", "High", "Medium", "Low"];
const PRIORITIES = ["", "P1", "P2", "P3", "P4"];
const CHANNELS = ["", "SMS", "Email", "IVR", "Push Notification", "In-App", "Call Center"];
const ECOSYSTEMS = ["", "fully_adopted", "partial_ecosystem", "rubika_only", "ewano_only", "hamrahman_only", "non_ecosystem", "volte_only"];

const EXEC_FILTER_TIERS: Record<string, string> = {
  "": "filter.allTiers",
  "Very High": "filter.critical",
  High: "filter.atRisk",
  Medium: "filter.watchlist",
  Low: "filter.stable",
};

type QuickChip = "escalation" | "human-touch" | "digital-only";

export default function QueuePage() {
  const { t, dir, locale } = useI18n();
  const [data, setData] = useState<RecommendationListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [loading, setLoading] = useState(true);
  const [detailItem, setDetailItem] = useState<RecommendationItem | null>(null);

  const [tab, setTab] = useState<QueueTab>("all");
  const [riskTier, setRiskTier] = useState("");
  const [priority, setPriority] = useState("");
  const [channel, setChannel] = useState("");
  const [ecosystemSegment, setEcosystemSegment] = useState("");
  const [sortBy, setSortBy] = useState<SortField>("campaign_queue_rank");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [quickChips, setQuickChips] = useState<QuickChip[]>([]);

  const QUEUE_TABS: { key: QueueTab; labelKey: string }[] = [
    { key: "all", labelKey: "queue.all" },
    { key: "high-risk", labelKey: "queue.highRisk" },
    { key: "p1", labelKey: "queue.p1" },
    { key: "digital-only", labelKey: "queue.digitalOnly" },
    { key: "human-touch", labelKey: "queue.humanTouch" },
  ];

  const load = useCallback(() => {
    setLoading(true);
    const q = new URLSearchParams({ page: String(page), page_size: String(pageSize), sort_by: sortBy, sort_dir: sortDir });

    let path = "/recommendations";
    if (tab === "high-risk") {
      path = "/recommendations/action-queue/high-risk";
    } else if (tab === "p1") {
      path = `/recommendations/action-queue/campaign/P1`;
    } else if (tab === "digital-only") {
      path = "/recommendations/action-queue/digital-only";
    } else if (tab === "human-touch") {
      path = "/recommendations/action-queue/human-touch";
    } else {
      if (riskTier) q.set("risk_tier", riskTier);
      if (priority) q.set("campaign_priority", priority);
      if (channel) q.set("channel", channel);
      if (ecosystemSegment) q.set("ecosystem_segment", ecosystemSegment);
    }

    api<RecommendationListResponse>(`${path}?${q}`)
      .then(setData)
      .finally(() => setLoading(false));
  }, [page, pageSize, tab, riskTier, priority, channel, ecosystemSegment, sortBy, sortDir]);

  useEffect(() => { load(); }, [load]);

  function handleTabChange(newTab: QueueTab) {
    setTab(newTab);
    setPage(1);
    setRiskTier("");
    setPriority("");
    setChannel("");
    setEcosystemSegment("");
    setQuickChips([]);
    setDetailItem(null);
  }

  function toggleChip(chip: QuickChip) {
    setQuickChips((prev) => prev.includes(chip) ? prev.filter((c) => c !== chip) : [...prev, chip]);
    setPage(1);
  }

  function handleSort(key: string) {
    if (key === sortBy) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(key as SortField);
      setSortDir("asc");
    }
    setPage(1);
  }

  async function exportCsv() {
    const blob = await apiBlob(`/reports/export/csv${priority ? `?priority=${priority}` : ""}`);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "action_queue.csv";
    a.click();
  }

  function renderItem(item: Record<string, unknown>) {
    return item as unknown as RecommendationItem;
  }

  const fr = t("common.unknown");

  const filteredItems = (data?.items ?? []).filter((item) => {
    if (quickChips.length === 0) return true;
    return quickChips.every((chip) => {
      if (chip === "escalation") return item.escalation_required;
      if (chip === "human-touch") return item.human_touch_flag;
      if (chip === "digital-only") return item.digital_only_flag;
      return true;
    });
  });

  const columns = [
    {
      key: "subscriber_id",
      header: t("queue.columns.id"),
      sortable: true,
      className: "w-16",
      render: (item: Record<string, unknown>) => {
        const r = renderItem(item);
        return (
          <Link href={`/subscribers/${r.subscriber_id}`} className="font-medium text-indigo-600 hover:underline">
            {r.subscriber_id}
          </Link>
        );
      },
    },
    {
      key: "risk_tier",
      header: t("queue.columns.tier"),
      sortable: true,
      className: "w-28",
      render: (item: Record<string, unknown>) => <ExecutiveRiskBadge tier={renderItem(item).risk_tier} />,
    },
    {
      key: "rule_id",
      header: t("queue.columns.rule"),
      className: "min-w-[160px] max-w-[220px]",
      render: (item: Record<string, unknown>) => <RuleLabel ruleId={renderItem(item).rule_id} showTechnical={false} />,
    },
    {
      key: "recommended_action",
      header: t("queue.columns.action"),
      className: "min-w-[240px] max-w-sm",
      render: (item: Record<string, unknown>) => {
        const r = renderItem(item);
        const narrative = buildRecommendationNarrative(r.rule_id, r.recommended_action);
        return (
          <span className="block text-sm leading-snug text-slate-700" title={narrative.retentionObjective}>
            {narrative.fullActionText}
          </span>
        );
      },
    },
    {
      key: "final_top_driver",
      header: t("queue.columns.driver"),
      className: "min-w-[140px] max-w-[200px]",
      render: (item: Record<string, unknown>) => {
        const driver = renderItem(item).final_top_driver;
        return (
          <span className="block text-sm leading-snug text-slate-600">
            {getExecutiveDriver(driver)}
          </span>
        );
      },
    },
    {
      key: "why_surfaced",
      header: t("queue.whySurfaced"),
      className: "min-w-[160px] max-w-[220px]",
      render: (item: Record<string, unknown>) => {
        const r = renderItem(item);
        const entry = getCatalogEntry(r.rule_id);
        if (!entry) return <span className="text-xs text-slate-400">{t("queue.ruleTrigger")}</span>;
        return (
          <span className="block text-xs leading-snug text-slate-600">
            {entry.retentionObjective}
          </span>
        );
      },
    },
    {
      key: "campaign_priority",
      header: t("queue.columns.priority"),
      sortable: true,
      className: "w-20",
      render: (item: Record<string, unknown>) => {
        const r = renderItem(item);
        return (
          <div className="flex items-center gap-1">
            {r.escalation_required && (
              <span className="inline-block h-2 w-2 rounded-full bg-red-500" title={t("queue.chipEscalation")} />
            )}
            <PriorityBadge priority={r.campaign_priority} />
          </div>
        );
      },
    },
    {
      key: "primary_channel",
      header: t("queue.columns.channel"),
      className: "w-24",
      render: (item: Record<string, unknown>) => (
        <span className="text-xs text-slate-500">{renderItem(item).primary_channel || fr}</span>
      ),
    },
    {
      key: "ecosystem_segment",
      header: t("queue.columns.segment"),
      sortable: true,
      className: "w-28",
      render: (item: Record<string, unknown>) => {
        const seg = renderItem(item).ecosystem_segment;
        return (
          <span className="text-xs text-slate-500">{getExecutiveEcosystemSegment(seg)}</span>
        );
      },
    },
    {
      key: "churn_probability",
      header: t("queue.columns.risk"),
      sortable: true,
      className: "w-16",
      render: (item: Record<string, unknown>) => {
        const r = renderItem(item);
        return <span className="font-medium text-xs">{formatPercent(r.churn_probability, locale)}</span>;
      },
    },
  ];

  function queueSubtitle() {
    switch (tab) {
      case "high-risk": return t("queue.queueHighRisk");
      case "p1": return t("queue.queueP1");
      case "digital-only": return t("queue.queueDigitalOnly");
      case "human-touch": return t("queue.queueHumanTouch");
      default: return "";
    }
  }

  return (
    <div className="space-y-4" dir={dir}>
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t("queue.title")}</h1>
          <p className="text-sm text-slate-500">{t("queue.description")}</p>
          <p className="mt-2 text-xs leading-relaxed text-slate-400 max-w-2xl">{t("queue.whyThisMatters")}</p>
        </div>
        <button
          onClick={exportCsv}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500"
        >
          {t("queue.exportCsv")}
        </button>
      </header>

      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-1">
        {QUEUE_TABS.map(({ key, labelKey }) => (
          <button
            key={key}
            onClick={() => handleTabChange(key)}
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

      <div className="flex flex-wrap items-center gap-2">
        {([
          { key: "escalation" as QuickChip, label: `🔴 ${t("queue.chipEscalation")}` },
          { key: "human-touch" as QuickChip, label: `👤 ${t("queue.chipHumanTouch")}` },
          { key: "digital-only" as QuickChip, label: `🤖 ${t("queue.chipDigitalOnly")}` },
        ]).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => toggleChip(key)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              quickChips.includes(key)
                ? "border-indigo-300 bg-indigo-50 text-indigo-700"
                : "border-slate-200 bg-white text-slate-500 hover:border-slate-300"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "all" && (
        <div className="flex flex-wrap gap-3">
          <Select
            options={RISK_TIERS.map((tier) => ({ value: tier, label: tier ? t(`queue.${EXEC_FILTER_TIERS[tier]}`) : t("queue.filter.allTiers") }))}
            value={riskTier}
            onChange={(v) => { setRiskTier(v); setPage(1); }}
          />
          <Select
            options={PRIORITIES.map((p) => ({ value: p, label: p || t("queue.filter.allPriorities") }))}
            value={priority}
            onChange={(v) => { setPriority(v); setPage(1); }}
          />
          <Select
            options={CHANNELS.map((c) => ({ value: c, label: c || t("queue.filter.allChannels") }))}
            value={channel}
            onChange={(v) => { setChannel(v); setPage(1); }}
          />
          <Select
            options={ECOSYSTEMS.map((e) => ({ value: e, label: e ? getExecutiveEcosystemSegment(e) : t("queue.filter.allSegments") }))}
            value={ecosystemSegment}
            onChange={(v) => { setEcosystemSegment(v); setPage(1); }}
          />
        </div>
      )}

      {tab !== "all" && (
        <Card className="bg-indigo-50 border-indigo-200">
          <CardTitle>{t("queue.queueInfo", { count: data?.total ?? 0 })}</CardTitle>
          <p className="mt-1 text-xs text-indigo-600">{queueSubtitle()}</p>
          <p className="mt-2 text-xs text-indigo-500 leading-relaxed">{t("queue.whyThisMatters")}</p>
        </Card>
      )}

      {loading ? (
        <PageLoading />
      ) : (
        <ErrorBoundary section="Recommendation queue table">
          {quickChips.length > 0 && (
            <p className="text-xs text-slate-500">
              {t("queue.chipActiveLabel", { count: formatNumber(filteredItems.length, locale), total: formatNumber(data?.total ?? 0, locale) })}
              {quickChips.includes("escalation") && ` (${t("queue.chipActiveEscalation")})`}
              {quickChips.includes("human-touch") && ` (${t("queue.chipActiveHumanTouch")})`}
              {quickChips.includes("digital-only") && ` (${t("queue.chipActiveDigitalOnly")})`}
            </p>
          )}
          <DataTable
            columns={columns}
            data={filteredItems as unknown as Record<string, unknown>[]}
            keyField="subscriber_id"
            emptyMessage={quickChips.length > 0 ? t("queue.chipEmpty") : t("queue.empty")}
            sortKey={sortBy}
            sortDir={sortDir}
            onSort={handleSort}
            onRowClick={(item) => {
              const r = renderItem(item);
              setDetailItem(detailItem?.subscriber_id === r.subscriber_id ? null : r);
            }}
          />
          {detailItem && (
            <div className="space-y-4">
              <NarrativeCard
                narrative={buildRecommendationNarrative(detailItem.rule_id, detailItem.recommended_action)}
              />
              <TechnicalDrawer
                title={t("queue.technicalDrawerTitle", { id: detailItem.subscriber_id })}
                items={[
                  { label: "Subscriber ID", value: detailItem.subscriber_id, mono: true },
                  { label: "Rule ID", value: detailItem.rule_id, mono: true },
                  { label: "Risk Tier (raw)", value: detailItem.risk_tier, mono: true },
                  { label: "Campaign Priority (raw)", value: detailItem.campaign_priority, mono: true },
                  { label: "Cost Tier", value: getCostTierLabel(detailItem.campaign_cost_tier) },
                  { label: "Cost Tier (raw)", value: detailItem.campaign_cost_tier, mono: true },
                  { label: "CRM Queue", value: getCrmQueueLabel(detailItem.crm_queue) },
                  { label: "CRM Queue (raw)", value: detailItem.crm_queue, mono: true },
                  { label: "Queue Rank", value: detailItem.campaign_queue_rank, mono: true },
                  { label: "Intervention Type", value: getInterventionTypeLabel(detailItem.intervention_type) },
                  { label: "Intervention Type (raw)", value: detailItem.intervention_type, mono: true },
                  { label: "Retention Strategy", value: getRetentionStrategyLabel(detailItem.ecosystem_retention_strategy) },
                  { label: "Retention Strategy (raw)", value: detailItem.ecosystem_retention_strategy, mono: true },
                  { label: "Digital Only", value: detailItem.digital_only_flag ? "Yes" : "No" },
                  { label: "Escalation Required", value: detailItem.escalation_required ? "Yes" : "No" },
                  { label: "Human Touch", value: detailItem.human_touch_flag ? "Yes" : "No" },
                  { label: "Raw Score", value: detailItem.churn_probability_raw != null ? `${(detailItem.churn_probability_raw * 100).toFixed(2)}%` : "—" },
                  { label: "Primary Channel", value: detailItem.primary_channel || "—" },
                  { label: "Secondary Channel", value: detailItem.secondary_channel || "—" },
                ]}
              />
            </div>
          )}
          <Pagination
            page={page}
            pageSize={pageSize}
            total={quickChips.length > 0 ? filteredItems.length : data?.total ?? 0}
            onPageChange={setPage}
            labelPrev={t("queue.prev")}
            labelNext={t("queue.next")}
            labelTotal={t("queue.total")}
            locale={locale}
          />
        </ErrorBoundary>
      )}
    </div>
  );
}
