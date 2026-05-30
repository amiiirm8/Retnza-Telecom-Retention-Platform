"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { DataTable } from "@/components/ui/table";
import { Pagination } from "@/components/ui/pagination";
import { PriorityBadge, ExecutiveRiskBadge } from "@/components/ui/badge";
import { RuleLabel } from "@/components/ui/rule-label";
import { PageLoading } from "@/components/ui/loading";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { Card } from "@/components/ui/card";
import { useI18n } from "@/i18n/provider";
import { getExecutiveEcosystemSegment, getFullActionText, getExecutiveDriver } from "@/lib/label-resolver";
import { formatPercent, formatNumber } from "@/lib/format";
import type { RecommendationListResponse } from "@/types/api";

export default function SubscribersListPage() {
  const { t, dir, locale } = useI18n();
  const [data, setData] = useState<RecommendationListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailId, setDetailId] = useState<number | null>(null);
  const fr = t("common.unknown");

  const load = useCallback(() => {
    setLoading(true);
    const q = new URLSearchParams({ page: String(page), page_size: String(pageSize), sort_by: "campaign_queue_rank", sort_dir: "asc" });
    if (search) q.set("search", search);
    api<RecommendationListResponse>(`/recommendations?${q}`)
      .then(setData)
      .finally(() => setLoading(false));
  }, [page, pageSize, search]);

  useEffect(() => { load(); }, [load]);

  const columns = [
    {
      key: "subscriber_id",
      header: t("subscribers.columns.id"),
      className: "w-16",
      render: (item: Record<string, unknown>) => {
        const id = item.subscriber_id as number;
        return (
          <Link href={`/subscribers/${id}`} className="font-medium text-indigo-600 hover:underline">
            #{formatNumber(id, locale)}
          </Link>
        );
      },
    },
    {
      key: "risk_tier",
      header: t("subscribers.columns.tier"),
      className: "w-24",
      render: (item: Record<string, unknown>) => <ExecutiveRiskBadge tier={item.risk_tier as string | null} />,
    },
    {
      key: "rule_id",
      header: t("subscribers.columns.rule"),
      className: "min-w-[160px] max-w-[220px]",
      render: (item: Record<string, unknown>) => <RuleLabel ruleId={item.rule_id as string | null} />,
    },
    {
      key: "recommended_action",
      header: t("subscribers.columns.action"),
      className: "min-w-[200px] max-w-xs",
      render: (item: Record<string, unknown>) => (
        <span className="block text-sm leading-snug text-slate-600">
          {getFullActionText(item.recommended_action as string | null)}
        </span>
      ),
    },
    {
      key: "final_top_driver",
      header: t("subscribers.columns.driver"),
      className: "min-w-[140px] max-w-[200px]",
      render: (item: Record<string, unknown>) => (
        <span className="block text-sm leading-snug text-slate-500">
          {getExecutiveDriver(item.final_top_driver as string | null)}
        </span>
      ),
    },
    {
      key: "churn_probability",
      header: t("subscribers.columns.risk"),
      className: "w-16",
      render: (item: Record<string, unknown>) => {
        const v = item.churn_probability as number | null;
        return <span className="font-medium text-xs">{v != null ? formatPercent(v, locale) : fr}</span>;
      },
    },
    {
      key: "campaign_priority",
      header: t("subscribers.columns.priority"),
      className: "w-16",
      render: (item: Record<string, unknown>) => <PriorityBadge priority={item.campaign_priority as string | null} />,
    },
    {
      key: "ecosystem_segment",
      header: t("subscribers.columns.segment"),
      className: "w-24",
      render: (item: Record<string, unknown>) => (
        <span className="text-xs text-slate-500">{getExecutiveEcosystemSegment(item.ecosystem_segment as string | null)}</span>
      ),
    },
  ];

  return (
    <div className="space-y-4" dir={dir}>
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t("subscribers.title")}</h1>
          <p className="text-sm text-slate-500">{t("subscribers.description")}</p>
        </div>
      </header>

      <div className="flex gap-3">
        <input
          type="number"
          placeholder={t("subscribers.searchPlaceholder")}
          className="w-64 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
        />
        {data && (
          <div className="flex items-center text-xs text-slate-400">
            {t("queue.total", { count: formatNumber(data.total, locale), page: formatNumber(page, locale), pages: formatNumber(Math.ceil(data.total / pageSize), locale) })}
          </div>
        )}
      </div>

      {loading ? (
        <PageLoading />
      ) : (
        <ErrorBoundary section="Subscribers table">
          <DataTable
            columns={columns}
            data={(data?.items ?? []) as unknown as Record<string, unknown>[]}
            keyField="subscriber_id"
            emptyMessage={t("subscribers.empty")}
            onRowClick={(item) => {
              const id = item.subscriber_id as number;
              setDetailId(detailId === id ? null : id);
            }}
          />
          {detailId != null && data?.items && (() => {
            const item = data.items.find((i) => i.subscriber_id === detailId);
            if (!item) return null;
            return (
              <Card className="border-indigo-200 bg-indigo-50/50">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-xs font-medium text-indigo-600 uppercase tracking-wider">{t("subscribers.profileCard")}</p>
                    <p className="mt-1 text-sm text-slate-700">
                      <span className="font-medium">{t("subscriber.recommendation")}:</span> {getFullActionText(item.recommended_action)}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      {t("subscriber.segment")}: {getExecutiveEcosystemSegment(item.ecosystem_segment)} —
                      {t("subscribers.columns.driver")}: {getExecutiveDriver(item.final_top_driver)}
                    </p>
                  </div>
                  <Link
                    href={`/subscribers/${item.subscriber_id}`}
                    className="shrink-0 rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
                  >
                    {t("subscribers.viewProfile")}
                  </Link>
                </div>
              </Card>
            );
          })()}
          <Pagination
            page={page}
            pageSize={pageSize}
            total={data?.total ?? 0}
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
