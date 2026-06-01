"use client";

import { useEffect, useMemo, useState } from "react";
import { useI18n } from "@/i18n/provider";
import { Card, CardTitle } from "@/components/ui/card";
import { ChartWrapper } from "@/components/ui/chart-wrapper";
import { CompatBadge } from "@/components/ui/badge";
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
import { formatNumber, formatPercent } from "@/lib/format";

import type { ModelHealth, EDAResponse, EDAChurnRow } from "@/types/api";

const questions = [
  "q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8",
] as const;

const confidenceColors: Record<string, string> = {
  strong: "bg-emerald-100 text-emerald-800 border-emerald-300",
  moderate: "bg-amber-100 text-amber-800 border-amber-300",
  mixed: "bg-orange-100 text-orange-800 border-orange-300",
  weak: "bg-slate-100 text-slate-500 border-slate-300",
};

const EDA_CARD_COLORS: Record<string, string> = {
  prepaid: "#ef4444",
  postpaid: "#10b981",
  "0-6": "#ef4444",
  "7-12": "#f59e0b",
  "13-24": "#3b82f6",
  "25-60": "#8b5cf6",
  "61+": "#10b981",
  "2G": "#10b981",
  "3G": "#3b82f6",
  "4G": "#f59e0b",
  "5G": "#ef4444",
  yes: "#10b981",
  no: "#ef4444",
};

function getConfidence(questionId: string): { label: string; level: string; basis: string; evidenceLayers: string[] } {
  const map: Record<string, { level: string; basis: string; evidenceLayers: string[] }> = {
    q1: {
      level: "strong",
      basis: "EDA + SHAP + model + rules agree on the same top features. No contradictory evidence.",
      evidenceLayers: ["EDA", "SHAP", "Model", "Recommendation Rules"],
    },
    q2: {
      level: "strong",
      basis: "All 4 analysis layers show the same 6.3× gap. No contradictory signal across any artifact.",
      evidenceLayers: ["EDA", "SHAP", "Model", "Recommendation Rules"],
    },
    q3: {
      level: "weak",
      basis: "Spend/revenue group SHAP is 49× weaker than predictive core. Bill shock rule covers small low-risk population. However, this finding may be dataset-specific.",
      evidenceLayers: ["SHAP", "Rule Diagnostics"],
    },
    q4: {
      level: "strong",
      basis: "Stratified EDA shows confounding clearly. SHAP interaction feature confirms the combined signal. Consistent across all layers.",
      evidenceLayers: ["EDA", "SHAP", "Model", "Behavioral Segments"],
    },
    q5: {
      level: "mixed",
      basis: "Descriptive association present but fully confounded by SIM type. Project docs explicitly call these 'segment markers' — not causal factors.",
      evidenceLayers: ["EDA", "SHAP", "Model"],
    },
    q6: {
      level: "mixed",
      basis: "VoLTE protective signal is consistent across EDA, SHAP, and rules (strong). Operator app signal is confounded by prepaid status (weak). Mixed evidence overall.",
      evidenceLayers: ["EDA", "SHAP", "Recommendation Rules"],
    },
    q7: {
      level: "strong",
      basis: "All demographic features have near-zero SHAP values. Raw churn rates by gender and age are near-identical. No rules target demographics.",
      evidenceLayers: ["EDA", "SHAP", "Model"],
    },
    q8: {
      level: "strong",
      basis: "End-to-end design is deterministic, documented, and governance-checked. Simulation provides realistic impact estimates.",
      evidenceLayers: ["Recommendation Rules", "Governance", "Retention Simulation"],
    },
  };
  const entry = map[questionId] ?? { level: "moderate", basis: "Present in some layers but not all.", evidenceLayers: [] };
  const key = `evidence.confidence.${entry.level}`;
  return { label: key, level: entry.level, basis: entry.basis, evidenceLayers: entry.evidenceLayers };
}

function buildInsightCards(eda: EDAResponse | null, locale: string) {
  if (!eda) return [];
  const cards: { title: string; value: string; insight: string; evidenceLevel: string }[] = [];

  // Prepaid vs Postpaid
  const prepaid = eda.churn_by_sim.find((r) => String(r.sim_card_type) === "prepaid");
  const postpaid = eda.churn_by_sim.find((r) => String(r.sim_card_type) === "postpaid");
  if (prepaid && postpaid) {
    const gap = prepaid.churn_rate / postpaid.churn_rate;
    cards.push({
      title: "Prepaid vs Postpaid Churn Gap",
      value: `${formatPercent(prepaid.churn_rate - postpaid.churn_rate, locale)} gap`,
      insight: `Prepaid churns at ${formatPercent(prepaid.churn_rate, locale)} — ${gap.toFixed(1)}× the postpaid rate of ${formatPercent(postpaid.churn_rate, locale)}. SIM type is the #1 SHAP driver globally.`,
      evidenceLevel: "strong",
    });
  }

  // Early tenure churn
  const earlyTenure = eda.churn_by_tenure.find((r) => String(r.tenure_band) === "0-6");
  if (earlyTenure) {
    cards.push({
      title: "Early-Life Churn Risk",
      value: `${formatPercent(earlyTenure.churn_rate, locale)} in first 6 months`,
      insight: `Subscribers in their first 6 months churn at ${formatPercent(earlyTenure.churn_rate, locale)} — 2× the base rate. Tenure is the #3 SHAP driver. Early intervention is critical.`,
      evidenceLevel: "strong",
    });
  }

  // 5G prepaid
  const prepaid5g = eda.churn_by_sim_and_generation.find(
    (r) => String(r.sim_card_type) === "prepaid" && String(r.mobile_data_generation) === "5G",
  );
  if (prepaid5g) {
    cards.push({
      title: "Prepaid 5G Risk Cluster",
      value: `${formatPercent(prepaid5g.churn_rate, locale)} churn rate`,
      insight: `Prepaid subscribers on 5G networks churn at ${formatPercent(prepaid5g.churn_rate, locale)} — the single highest-risk segment. The prepaid_5g_risk_flag is the #2 SHAP driver.`,
      evidenceLevel: "strong",
    });
  }

  // VoLTE protective effect
  const volteYes = eda.volte_impact.find((r) => String(r.volte_service) === "yes");
  const volteNo = eda.volte_impact.find((r) => String(r.volte_service) === "no");
  if (volteYes && volteNo) {
    const diff = volteNo.churn_rate - volteYes.churn_rate;
    cards.push({
      title: "VoLTE Protective Effect",
      value: `${formatPercent(diff, locale)} lower churn with VoLTE`,
      insight: `VoLTE adopters churn at ${formatPercent(volteYes.churn_rate, locale)} vs ${formatPercent(volteNo.churn_rate, locale)} for non-adopters. VoLTE non-adopter flag is the #5 SHAP driver. Digital adoption correlates with retention.`,
      evidenceLevel: "mixed",
    });
  }

  // Gender equality
  cards.push({
    title: "Demographics: No Churn Signal",
    value: "Gender & age show no differentiation",
    insight: "All demographic features have near-zero SHAP values. Churn rates by gender (49.5% F / 50.5% M) and age cohort (5 bands) are all ~26-27%. Retention strategy should not target demographics.",
    evidenceLevel: "strong",
  });

  // Base rate with top SHAP features
  cards.push({
    title: "Top Predictive Signals",
    value: `${eda.top_shap_features.slice(0, 3).join(", ")}`,
    insight: `The model identifies ${eda.top_shap_features.length > 0 ? eda.top_shap_features.slice(0, 5).join(", ") : "SIM type, tenure, and generation"} as the strongest churn predictors. These align with the EDA findings above.`,
    evidenceLevel: "strong",
  });

  return cards;
}

function buildEdaChartData(eda: EDAResponse | null, key: keyof EDAResponse, nameKey: string, colorKey: string) {
  void colorKey;
  const rows = (eda?.[key] as EDAChurnRow[] | undefined) ?? [];
  return rows.map((r) => ({
    name: String(r[nameKey as keyof EDAChurnRow] ?? ""),
    churnRate: +(r.churn_rate * 100).toFixed(1),
    n: r.n,
    fill: EDA_CARD_COLORS[String(r[nameKey as keyof EDAChurnRow] ?? "")] ?? "#4f46e5",
  }));
}

function formatRelativeTime(utcStr: string, locale: string): string {
  void locale;
  if (!utcStr) return "—";
  const now = Date.now();
  const then = new Date(utcStr).getTime();
  const hours = Math.floor((now - then) / 3600000);
  if (hours < 1) return "< 1 hour ago";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function EvidencePage() {
  const { t, dir, locale } = useI18n();
  const [health, setHealth] = useState<ModelHealth | null>(null);
  const [eda, setEda] = useState<EDAResponse | null>(null);
  const [, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api<ModelHealth>("/model/health").catch(() => null),
      api<EDAResponse>("/dashboard/eda").catch(() => null),
    ])
      .then(([h, e]) => {
        setHealth(h);
        setEda(e);
      })
      .finally(() => setLoading(false));
  }, []);

  const insightCards = useMemo(() => buildInsightCards(eda, locale), [eda, locale]);

  const simChartData = useMemo(() => buildEdaChartData(eda, "churn_by_sim", "sim_card_type", ""), [eda]);
  const tenureChartData = useMemo(() => buildEdaChartData(eda, "churn_by_tenure", "tenure_band", ""), [eda]);
  const genChartData = useMemo(() => buildEdaChartData(eda, "churn_by_generation", "mobile_data_generation", ""), [eda]);

  const evidenceNarrative = eda?.executive_narratives?.find((n) => n.key === "churn_landscape");
  const ecosystemNarrative = eda?.executive_narratives?.find((n) => n.key === "ecosystem_observations");

  return (
    <div className="space-y-8" dir={dir}>
      <header>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-900">{t("evidence.title")}</h1>
          {health && <CompatBadge status={health.compatibility_status} />}
        </div>
        <p className="mt-1 text-sm text-slate-500">{t("evidence.description")}</p>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          {health?.artifact_freshness && (
            <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-[10px] font-medium text-slate-500 shrink-0">
              {t("evidence.freshness.title")}: {health.champion_family}
            </span>
          )}
          {eda?.generated_at_utc && (
            <span className="text-[11px] text-slate-400">
              {t("evidence.freshness.lastRefreshed")}: {formatRelativeTime(eda.generated_at_utc, locale)}
            </span>
          )}
        </div>
      </header>

      {/* ── Data-Driven Insight Cards ──────────────────────────────────── */}
      {insightCards.length > 0 && (
        <Card className="border-l-4 border-l-teal-500">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-teal-900">{t("evidence.edaInsights.title")}</h2>
            <span className="rounded-full bg-teal-100 px-2 py-0.5 text-[10px] font-medium text-teal-700">
              {insightCards.length} data-driven findings
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">{t("evidence.edaInsights.desc")}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {insightCards.map((card, i) => (
              <div
                key={i}
                className={`rounded-lg border p-3 ${
                  card.evidenceLevel === "strong"
                    ? "border-teal-100 bg-teal-50/50"
                    : "border-amber-100 bg-amber-50/50"
                }`}
              >
                <p className="text-[10px] font-bold uppercase tracking-wider text-teal-600">
                  {card.title}
                </p>
                <p className="mt-1 text-lg font-bold text-slate-900">{card.value}</p>
                <p className="mt-1 text-xs leading-relaxed text-slate-700">{card.insight}</p>
                <span
                  className={`mt-2 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                    card.evidenceLevel === "strong"
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-amber-100 text-amber-700"
                  }`}
                >
                  {card.evidenceLevel === "strong" ? "Strong Evidence" : "Mixed Evidence"}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── EDA Charts ─────────────────────────────────────────────────── */}
      {eda && (
        <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
          {simChartData.length > 0 && (
            <div className="space-y-2">
              <ChartWrapper
                title="Churn Rate by SIM Type"
                subtitle="Prepaid vs postpaid churn — the defining risk signal in this dataset"
                className="h-64"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={simChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 11 }} domain={[0, 60]} tickFormatter={(v) => `${v}%`} />
                    <Tooltip formatter={(v: unknown) => [`${typeof v === 'number' ? v.toFixed(1) : '?'}%`, "Churn Rate"]} />
                    <Bar dataKey="churnRate" radius={[4, 4, 0, 0]}>
                      {simChartData.map((entry, idx) => (
                        <Cell key={idx} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartWrapper>
              <p className="text-xs text-slate-500 leading-relaxed px-1">
                Prepaid subscribers churn at {simChartData.find(d => d.name === "prepaid")?.churnRate?.toFixed(1) ?? "?"}% — {simChartData.find(d => d.name === "prepaid")?.churnRate ? (simChartData.find(d => d.name === "prepaid")!.churnRate / simChartData.find(d => d.name === "postpaid")!.churnRate).toFixed(1) : "?"}× the postpaid rate. SIM type is the #1 SHAP driver globally. This is the single most actionable risk signal in the dataset.
              </p>
            </div>
          )}
          {tenureChartData.length > 0 && (
            <div className="space-y-2">
              <ChartWrapper
                title="Churn Rate by Tenure"
                subtitle="Early-life subscribers (0-6 months) show dramatically higher churn"
                className="h-64"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={tenureChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} domain={[0, 60]} tickFormatter={(v) => `${v}%`} />
                    <Tooltip formatter={(v: unknown) => [`${typeof v === 'number' ? v.toFixed(1) : '?'}%`, "Churn Rate"]} />
                    <Bar dataKey="churnRate" radius={[4, 4, 0, 0]}>
                      {tenureChartData.map((entry, idx) => (
                        <Cell key={idx} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartWrapper>
              <p className="text-xs text-slate-500 leading-relaxed px-1">
                New subscribers (0-6 month tenure) churn at {tenureChartData.find(d => d.name === "0-6")?.churnRate?.toFixed(1) ?? "?"}% — 2× the base rate. Risk drops steadily with tenure, reaching {tenureChartData.find(d => d.name === "61+")?.churnRate?.toFixed(1) ?? "?"}% for subscribers with 5+ years. Tenure is the #3 SHAP driver globally.
              </p>
            </div>
          )}
          {genChartData.length > 0 && (
            <div className="space-y-2">
              <ChartWrapper
                title="Churn Rate by Mobile Generation"
                subtitle="Higher generation correlates with higher churn (confounded by prepaid mix)"
                className="h-64"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={genChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} domain={[0, 60]} tickFormatter={(v) => `${v}%`} />
                    <Tooltip formatter={(v: unknown) => [`${typeof v === 'number' ? v.toFixed(1) : '?'}%`, "Churn Rate"]} />
                    <Bar dataKey="churnRate" radius={[4, 4, 0, 0]}>
                      {genChartData.map((entry, idx) => (
                        <Cell key={idx} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartWrapper>
              <p className="text-xs text-slate-500 leading-relaxed px-1">
                The 5G churn rate ({genChartData.find(d => d.name === "5G")?.churnRate?.toFixed(1) ?? "?"}%) is confounded by prepaid mix &mdash; prepaid 5G subscribers churn at 54.6%, postpaid 5G at only 13.9%. The prepaid 5G interaction is the #2 SHAP driver.
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── Summary Banner ─────────────────────────────────────────────── */}
      <Card className="border-indigo-200 bg-gradient-to-br from-indigo-50 to-white">
        <h2 className="text-base font-bold text-indigo-900">{t("evidence.summaryTitle")}</h2>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {eda ? (
            <>
              <div className="flex items-start gap-2 rounded-lg bg-indigo-100/60 p-2.5 text-sm text-indigo-900">
                <span className="mt-0.5 shrink-0 text-indigo-500">▸</span>
                <span>Base churn rate: {formatPercent(eda.mean_calibrated_risk, locale)} ({formatNumber(eda.n_subscribers, locale)} subscribers)</span>
              </div>
              {evidenceNarrative?.bullets?.slice(0, 4).map((bullet, i) => (
                <div key={i} className="flex items-start gap-2 rounded-lg bg-indigo-100/60 p-2.5 text-sm text-indigo-900">
                  <span className="mt-0.5 shrink-0 text-indigo-500">▸</span>
                  <span>{bullet}</span>
                </div>
              ))}
            </>
          ) : (
            (["overallChurn", "prepaidDominant", "topDriver", "ecosystemAssociation", "modelPerformance"] as const).map((key) => (
              <div key={key} className="flex items-start gap-2 rounded-lg bg-indigo-100/60 p-2.5 text-sm text-indigo-900">
                <span className="mt-0.5 shrink-0 text-indigo-500">▸</span>
                <span>{t(`evidence.summaryItems.${key}`)}</span>
              </div>
            ))
          )}
        </div>
      </Card>

      {/* ── Evidence Narrative from Executive Summary ──────────────────── */}
      {ecosystemNarrative && (
        <Card className="border-l-4 border-l-purple-500 bg-gradient-to-br from-purple-50 to-white">
          <h2 className="text-base font-bold text-purple-900">Ecosystem & Churn Observations</h2>
          <div className="mt-3 space-y-2">
            {ecosystemNarrative.bullets.slice(0, 6).map((bullet, i) => (
              <p key={i} className="text-sm text-purple-800 leading-relaxed">{bullet}</p>
            ))}
          </div>
        </Card>
      )}

      {/* ── Question Cards ────────────────────────────────────────────── */}
      <section className="space-y-6">
        {questions.map((qId) => {
          const { label: confKey, level, basis, evidenceLayers } = getConfidence(qId);
          const questionKey = `evidence.questions.${qId}`;
          const isEn = t("evidence.glossary.confidence")?.startsWith("Confidence");

          return (
            <Card key={qId} className="border-l-4 border-l-indigo-400">
              <div className="mb-4 flex items-start gap-3">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-bold text-indigo-700">
                  {qId.replace("q", "")}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium uppercase tracking-wider text-indigo-500">
                    {isEn ? "Question" : "سوال"}
                  </p>
                  <h3 className="mt-0.5 text-lg font-bold text-slate-900">
                    {t(`${questionKey}.question`)}
                  </h3>
                </div>
              </div>

              <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                <p className="text-xs font-medium uppercase tracking-wider text-emerald-600">
                  {isEn ? "Plain Answer" : "پاسخ ساده"}
                </p>
                <p className="mt-1 text-base font-semibold text-emerald-900">
                  {t(`${questionKey}.answer`)}
                </p>
              </div>

              <div className="mb-4 grid gap-4 lg:grid-cols-3">
                <div className="lg:col-span-1">
                  <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
                    {isEn ? "What the Numbers Mean" : "معنی اعداد"}
                  </p>
                  <p className="mt-1 text-sm leading-relaxed text-slate-700">
                    {t(`${questionKey}.numbersExplain`)}
                  </p>
                </div>

                <div className="lg:col-span-1">
                  <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
                    {isEn ? "Why We Trust This Answer" : "چرا به این پاسخ اعتماد داریم"}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span
                      className={`inline-block rounded-full border px-3 py-1 text-xs font-semibold ${confidenceColors[level] || confidenceColors.moderate}`}
                    >
                      {t(confKey)}
                    </span>
                    {evidenceLayers.map((layer) => (
                      <span
                        key={layer}
                        className="inline-block rounded-md bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-600"
                      >
                        {layer}
                      </span>
                    ))}
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-slate-700">
                    {t(`${questionKey}.trustWhy`)}
                  </p>
                  <p className="mt-1.5 text-xs italic text-slate-500">
                    {isEn ? `Confidence basis: ${basis}` : `مبنای اعتبار: ${basis}`}
                  </p>
                </div>

                <div className="lg:col-span-1">
                  <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
                    {isEn ? "Source Artifacts" : "مستندات منبع"}
                  </p>
                  <ul className="mt-2 space-y-1">
                    {(t(`${questionKey}.sources`) as string)
                      .split("|")
                      .filter(Boolean)
                      .slice(0, 4)
                      .map((src: string, i: number) => (
                        <li
                          key={i}
                          className="rounded-md bg-slate-50 px-2 py-1 font-mono text-[10px] text-slate-500"
                        >
                          {src.trim()}
                        </li>
                      ))}
                  </ul>
                </div>
              </div>

              <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
                  {isEn ? "What This Means for Retention" : "اهمیت این موضوع برای حفظ مشترک"}
                </p>
                <p className="mt-1 text-sm leading-relaxed text-slate-800">
                  {t(`${questionKey}.retentionAction`)}
                </p>
              </div>

              <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-4">
                <p className="text-xs font-medium uppercase tracking-wider text-amber-600">
                  {isEn ? "Caveats & Limitations" : "ملاحظات و محدودیت‌ها"}
                </p>
                <p className="mt-1 text-sm leading-relaxed text-amber-800">
                  {t(`${questionKey}.caveat`)}
                </p>
              </div>
            </Card>
          );
        })}
      </section>

      {/* ── Cross-Cutting Patterns ────────────────────────────────────── */}
      <Card className="border-l-4 border-l-amber-500">
        <h2 className="text-base font-bold text-amber-900">{t("evidence.patternsTitle")}</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {(["p1", "p2", "p3", "p4", "p5"] as const).map((pId) => (
            <div key={pId} className="rounded-lg border border-amber-200 bg-amber-50/60 p-3.5">
              <p className="text-sm font-semibold text-amber-900">
                {t(`evidence.patterns.${pId}.title`)}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-amber-800">
                {t(`evidence.patterns.${pId}.desc`)}
              </p>
            </div>
          ))}
        </div>
      </Card>

      {/* ── Operational Recommendations ───────────────────────────────── */}
      <Card className="border-l-4 border-l-emerald-500 bg-gradient-to-br from-emerald-50 to-white">
        <h2 className="text-base font-bold text-emerald-900">{t("evidence.actionsTitle")}</h2>
        <ul className="mt-3 space-y-2">
          {(["a1", "a2", "a3", "a4", "a5"] as const).map((aId) => (
            <li key={aId} className="flex items-start gap-2 text-sm text-slate-700">
              <span className="mt-0.5 shrink-0 text-emerald-600">✓</span>
              <span>{t(`evidence.actions.${aId}`)}</span>
            </li>
          ))}
        </ul>
      </Card>

      {/* ── Source References ─────────────────────────────────────────── */}
      <Card>
        <CardTitle>{t("evidence.references.title")}</CardTitle>
        <p className="mt-1 text-xs text-slate-500">{t("evidence.references.desc")}</p>
        <ul className="mt-3 space-y-1.5">
          {(["item1", "item2", "item3", "item4", "item5"] as const).map((rId) => (
            <li key={rId} className="rounded-md bg-slate-50 px-3 py-2 font-mono text-[11px] text-slate-600">
              {t(`evidence.references.${rId}`)}
            </li>
          ))}
        </ul>
      </Card>

      {/* ── Glossary ──────────────────────────────────────────────────── */}
      <Card>
        <CardTitle>{t("evidence.glossaryTitle")}</CardTitle>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(["shap", "calibratedRisk", "churnRate", "lift", "riskTier", "retentionPlay", "ecosystemSegment", "confidence"] as const).map((gKey) => (
            <div key={gKey} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs font-bold uppercase tracking-wider text-indigo-600">
                {gKey === "shap" ? "SHAP" :
                 gKey === "calibratedRisk" ? "Calibrated Risk" :
                 gKey === "churnRate" ? "Churn Rate" :
                 gKey === "lift" ? "Lift" :
                 gKey === "riskTier" ? "Risk Tier" :
                 gKey === "retentionPlay" ? "Retention Play" :
                 gKey === "ecosystemSegment" ? "Ecosystem Segment" :
                 "Confidence"}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-slate-600">
                {t(`evidence.glossary.${gKey}`)}
              </p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
