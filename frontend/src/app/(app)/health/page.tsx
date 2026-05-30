/**
 * Model Health Page — Model Operations Center
 *
 * Production-grade health monitoring for the champion churn prediction model.
 * This page functions as the Model Operations Center (ModelOps), surfacing:
 *
 * ── Architecture: Model Operations Flow ─────────────────────────────────────
 * Production Status Banner (compatibility + metric health)
 *   ↓ executive summary of deployment readiness
 * Performance Overview (PR-AUC, ROC-AUC, Brier, ECE cards)
 *   ↓ raw metric values at a glance
 * Score Interpretation (business meaning, telecom context, health ranges)
 *   ↓ each metric explained for non-technical reviewers
 * Configuration (champion family, calibration, threshold, policy)
 *   ↓ model identity and operational settings
 * Risk Tiers (thresholds for each risk band)
 *   ↓ how subscriber risk is categorized
 * Score Distribution + CV Stability Charts
 *   ↓ visual model behavior analysis
 * Drift & Population Stability (PSI by feature, severity badges, notes)
 *   ↓ population shift detection
 * Stability Explainability (CV fold consistency, σ-based severity)
 *   ↓ training stability assessment
 * Artifact Freshness (age tracking for all production artifacts)
 *   ↓ staleness warnings
 * Warnings (backend-reported issues)
 *   ↓ operational alerts
 *
 * Data contracts:
 * - GET /model/health → ModelHealth (metrics, config, thresholds)
 * - GET /model/drift → DriftResponse (PSI + monitoring)
 * - GET /model/stability → StabilityResponse (CV metrics)
 *
 * The page evaluates health using both backend compatibility status and
 * metric threshold checks (ECE < 0.05, PR-AUC > 0.3, Brier < 0.25).
 */

"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api } from "@/lib/api";
import { Card, CardTitle } from "@/components/ui/card";
import { KpiCard } from "@/components/ui/kpi-card";
import { CompatBadge } from "@/components/ui/badge";

import { PageLoading } from "@/components/ui/loading";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { ArtifactFreshnessList } from "@/components/governance/artifact-freshness-list";
import { ModelStatusBanner } from "@/components/governance/model-status-banner";
import { ScoreInterpretationCard } from "@/components/health/score-interpretation-card";
import { DriftExplainabilityCard } from "@/components/health/drift-explainability-card";
import { StabilityExplainabilityCard } from "@/components/health/stability-explainability-card";
import { useI18n } from "@/i18n/provider";
import { getPolicyRoleLabel } from "@/lib/governance-labels";
import { getRiskTierLabel, getRiskTierExplanation } from "@/lib/risk-labels";
import type { ModelHealth, DriftResponse, StabilityResponse } from "@/types/api";

export default function HealthPage() {
  const { t, dir, locale } = useI18n();
  const [health, setHealth] = useState<ModelHealth | null>(null);
  const [drift, setDrift] = useState<DriftResponse | null>(null);
  const [stability, setStability] = useState<StabilityResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api<ModelHealth>("/model/health"),
      api<DriftResponse>("/model/drift"),
      api<StabilityResponse>("/model/stability"),
    ])
      .then(([h, d, s]) => {
        setHealth(h);
        setDrift(d);
        setStability(s);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <PageLoading />;
  if (!health) return <p className="text-red-500">{t("common.error")}</p>;

  function histogramToData(hist: Record<string, unknown> | undefined): { name: string; value: number }[] {
    if (!hist || typeof hist !== "object") return [];
    const h = hist as { bin_edges?: number[]; counts?: number[] };
    const edges = h.bin_edges;
    const counts = h.counts;
    if (!edges || !counts || edges.length < 2) return [];
    return edges.slice(0, -1).map((start, i) => ({
      name: `${start.toFixed(1)}-${(edges[i + 1]).toFixed(1)}`,
      value: counts[i] ?? 0,
    }));
  }

  const firstHistKey = drift?.score_histograms
    ? Object.keys(drift.score_histograms).find((k) => {
        const v = (drift.score_histograms as Record<string, unknown>)[k];
        return typeof v === "object" && v !== null;
      })
    : null;
  const scoreHistogramData = firstHistKey
    ? histogramToData((drift!.score_histograms as Record<string, unknown>)[firstHistKey] as Record<string, unknown>)
    : [];

  const monitoringNotes = drift?.monitoring_notes || [];

  const cvData = stability?.cv_mean_std
    ? Object.entries(stability.cv_mean_std).map(([family, stats]) => ({
        name: family,
        "PR-AUC": stats.pr_auc_mean ?? 0,
        "ROC-AUC": stats.roc_auc_mean ?? 0,
        Brier: stats.brier_mean ?? 0,
      }))
    : [];

  const isCompatible = health.compatibility_status === "compatible";

  const riskTierEntries = health.threshold_policy?.risk_tier_thresholds
    ? Object.entries(health.threshold_policy.risk_tier_thresholds)
    : [];

  return (
    <div className="space-y-6" dir={dir}>
      <header>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-900">{t("health.title")}</h1>
          <CompatBadge status={health.compatibility_status} />
        </div>
        <p className="mt-1 text-sm text-slate-500">{t("health.description")}</p>
      </header>

      <ModelStatusBanner
        isCompatible={isCompatible}
        warningCount={health.warnings?.length ?? 0}
        prAuc={health.pr_auc}
        ece={health.ece}
        brier={health.brier}
        rocAuc={health.roc_auc}
        versionTag={health.version_tag}
        championFamily={health.champion_family}
        calibrationMethod={health.calibration_method}
        operatingThreshold={health.threshold_policy?.operating_threshold ?? null}
        operatingPolicy={health.threshold_policy?.operating_policy ?? null}
      />

      <section>
        <h2 className="mb-4 text-lg font-bold text-slate-800">{t("health.section.performance")}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard title={t("health.prAuc")} value={health.pr_auc?.toFixed(3) ?? "—"} subtitle={t("health.prAucWhy")} />
          <KpiCard title={t("health.rocAuc")} value={health.roc_auc?.toFixed(3) ?? "—"} subtitle={t("health.rocAucSubtitle")} />
          <KpiCard title={t("health.brier")} value={health.brier?.toFixed(3) ?? "—"} subtitle={t("health.brierWhy")} />
          <KpiCard title={t("health.ece")} value={health.ece?.toFixed(3) ?? "—"} subtitle={t("health.eceWhy")} />
        </div>

        <div className="mt-4">
          <ScoreInterpretationCard scores={[
            {
              label: t("health.prAuc"),
              value: health.pr_auc,
              businessMeaning: "Measures how well the model ranks churners above non-churners, focusing on the positive (churn) class. Higher is better.",
              telecomInterpretation: "A PR-AUC above 0.30 means the model can identify churners 3× better than random. Below 0.20 indicates the model struggles to distinguish churners from non-churners in your subscriber base.",
              acceptableRange: "0.20 – 0.50+ (telecom churn)",
              isHealthy: (health.pr_auc ?? 0) >= 0.3,
              isWarning: (health.pr_auc ?? 0) >= 0.2 && (health.pr_auc ?? 0) < 0.3,
              isCritical: (health.pr_auc ?? 0) < 0.2,
            },
            {
              label: t("health.rocAuc"),
              value: health.roc_auc,
              businessMeaning: "Measures overall ranking quality across all possible thresholds. Less sensitive to class imbalance than PR-AUC.",
              telecomInterpretation: "In telecom churn (5-15% base rate), ROC-AUC can appear inflated. PR-AUC is more informative. Use this as a secondary check.",
              acceptableRange: "0.70 – 0.90+",
              isHealthy: (health.roc_auc ?? 0) >= 0.75,
              isWarning: (health.roc_auc ?? 0) >= 0.65 && (health.roc_auc ?? 0) < 0.75,
              isCritical: (health.roc_auc ?? 0) < 0.65,
            },
            {
              label: t("health.brier"),
              value: health.brier,
              businessMeaning: "Measures the mean squared difference between predicted probabilities and actual outcomes. Lower is better.",
              telecomInterpretation: "A Brier score below 0.20 means churn probability estimates are reliable. Above 0.30 means the model's probability estimates are no better than guessing — CRM teams cannot trust the risk scores.",
              acceptableRange: "0.10 – 0.25",
              isHealthy: (health.brier ?? 1) < 0.2,
              isWarning: (health.brier ?? 1) >= 0.2 && (health.brier ?? 1) < 0.3,
              isCritical: (health.brier ?? 1) >= 0.3,
            },
            {
              label: t("health.ece"),
              value: health.ece,
              businessMeaning: "Measures calibration error — the average difference between predicted probability and actual outcome. Lower is better.",
              telecomInterpretation: "An ECE below 0.05 means predicted risk scores match observed churn rates closely. Above 0.10 means the model's probabilities are unreliable — a subscriber predicted at 70% risk may actually churn at 50% or 90%.",
              acceptableRange: "< 0.05 (good), < 0.10 (acceptable)",
              isHealthy: (health.ece ?? 1) < 0.05,
              isWarning: (health.ece ?? 1) >= 0.05 && (health.ece ?? 1) < 0.1,
              isCritical: (health.ece ?? 1) >= 0.1,
            },
          ]} />
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-bold text-slate-800">{t("health.section.configuration")}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="flex flex-col">
            <CardTitle>{t("health.championFamily")}</CardTitle>
            <p className="mt-2 text-base font-semibold text-slate-900">{health.champion_family}</p>
            <p className="mt-auto pt-3 text-xs leading-relaxed text-slate-400">{t("health.championFamilySubtitle")}</p>
          </Card>
          <Card className="flex flex-col">
            <CardTitle>{t("health.calibration")}</CardTitle>
            <p className="mt-2 text-base font-semibold text-slate-900">{health.calibration_method}</p>
            <p className="mt-auto pt-3 text-xs leading-relaxed text-slate-400">{t("health.calibrationSubtitle")}</p>
          </Card>
          <Card className="flex flex-col">
            <CardTitle>{t("health.operatingThreshold")}</CardTitle>
            <p className="mt-2 text-base font-semibold text-slate-900">{health.threshold_policy?.operating_threshold?.toFixed(4) ?? "—"}</p>
            <p className="mt-auto pt-3 text-xs leading-relaxed text-slate-400">{t("health.operatingThresholdSubtitle")}</p>
          </Card>
          <Card className="flex flex-col">
            <CardTitle>{t("health.policy")}</CardTitle>
            <p className="mt-2 text-base font-semibold text-slate-900">{getPolicyRoleLabel(health.threshold_policy?.operating_policy)}</p>
            <p className="mt-auto pt-3 text-xs leading-relaxed text-slate-400">{t("health.policySubtitle")}</p>
            <p className="mt-1 text-[10px] text-slate-400 leading-relaxed">{t("governance.explanation.primaryOperatingPolicy")}</p>
          </Card>
        </div>
      </section>

      <Card className="border-l-4 border-l-indigo-500 bg-gradient-to-br from-slate-50 to-white">
        <CardTitle>{t("health.configCallout.title")}</CardTitle>
        <p className="mt-2 text-xs leading-relaxed text-slate-600">{t("health.configCallout.body")}</p>
      </Card>

      {riskTierEntries.length > 0 && (
        <Card>
          <CardTitle>{t("health.riskTiers")}</CardTitle>
          <p className="mt-1 text-xs text-slate-400">{t("health.riskTiersDescription")}</p>
          <p className="mt-1 text-xs leading-relaxed text-slate-500">{t("health.riskTiersExplain")}</p>
          <div className="mt-3 space-y-1.5">
            {riskTierEntries.map(([tier, threshold]) => {
              const businessLabel = getRiskTierLabel(tier);
              const explanation = getRiskTierExplanation(tier);
              return (
                <div key={tier} className="flex items-center justify-between rounded-lg border bg-slate-50 px-4 py-2.5 text-sm">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="shrink-0 rounded-full bg-slate-200 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-slate-600">
                      {businessLabel}
                    </span>
                    <span className="text-xs text-slate-500 leading-snug">{explanation}</span>
                  </div>
                  <span className="shrink-0 ml-3 rtl:ml-0 rtl:mr-3 font-mono text-xs text-slate-400">
                    {typeof threshold === "number" ? threshold.toFixed(4) : String(threshold)}
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <ErrorBoundary section="Score distribution chart">
          {scoreHistogramData.length > 0 && (
            <Card className="flex flex-col p-5">
              <div className="mb-3">
                <CardTitle>{t("health.scoreDistribution")}</CardTitle>
                <p className="mt-1 text-xs text-slate-400">{t("health.scoreDistributionSubtitle")}</p>
              </div>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={scoreHistogramData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="value" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-slate-500">{t("health.scoreDistributionExplain")}</p>
              <p className="mt-1 text-[10px] leading-relaxed text-slate-400 italic">{t("health.scoreDistributionTakeaway")}</p>
            </Card>
          )}
        </ErrorBoundary>

        <ErrorBoundary section="CV stability chart">
          {cvData.length > 0 && (
            <Card className="flex flex-col p-5">
              <div className="mb-3">
                <CardTitle>{t("health.cvStability")}</CardTitle>
                <p className="mt-1 text-xs text-slate-400">{t("health.cvStabilitySubtitle")}</p>
              </div>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={cvData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="PR-AUC" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-slate-500">{t("health.cvStabilityExplain")}</p>
              <p className="mt-1 text-[10px] leading-relaxed text-slate-400 italic">{t("health.cvStabilityTakeaway")}</p>
            </Card>
          )}
        </ErrorBoundary>
      </div>

      <ErrorBoundary section="Drift explainability">
        <DriftExplainabilityCard
        driftSummary={drift?.drift_summary ?? null}
        psiReferences={drift?.psi_references ?? null}
        monitoringNotes={monitoringNotes}
      />
      </ErrorBoundary>

      <ErrorBoundary section="Stability explainability">
        <StabilityExplainabilityCard
          cvMeanStd={stability?.cv_mean_std ?? null}
          method={stability?.method ?? null}
          generatedAt={stability?.generated_at_utc ?? null}
          locale={locale}
        />
      </ErrorBoundary>

      <Card className="border-l-4 border-l-emerald-500 bg-gradient-to-br from-emerald-50 to-white">
        <CardTitle>{t("health.trustSummary.title")}</CardTitle>
        <p className="mt-2 text-xs leading-relaxed text-slate-600">{t("health.trustSummary.body")}</p>
      </Card>

      <ErrorBoundary section="Artifact freshness">
        <ArtifactFreshnessList artifacts={health.artifact_freshness} locale={locale} />
      </ErrorBoundary>

      {health.warnings && health.warnings.length > 0 && (
        <Card className="border-amber-200 bg-amber-50">
          <CardTitle>{t("health.warnings")}</CardTitle>
          <ul className="mt-2 space-y-1">
            {health.warnings.map((w, i) => (
              <li key={i} className="text-sm text-amber-700">{w}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
