/**
 * Drift Explainability Card
 *
 * Displays population stability analysis using PSI (Population Stability Index)
 * values for each model feature. Provides humanized interpretations:
 *
 * - PSI < 0.10: Stable — minor population shift, no action required
 * - PSI 0.10–0.25: Monitor — moderate shift detected
 * - PSI >= 0.25: Retraining Recommended — significant shift
 *
 * Each feature gets a severity badge (Stable / Monitor / Retraining Recommended)
 * and a plain-English interpretation. Monitoring notes from the backend are
 * displayed when available.
 */

import { Card, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/provider";

interface DriftExplainabilityCardProps {
  driftSummary: Record<string, unknown> | null;
  psiReferences: Record<string, unknown> | null;
  monitoringNotes: string[];
}

type SeverityLevel = "stable" | "monitor" | "retrain";

const DRIFT_LABEL_KEYS: Record<SeverityLevel, string> = {
  stable: "health.drift.stable",
  monitor: "health.drift.monitor",
  retrain: "health.drift.retrain",
};

const DRIFT_COLORS: Record<SeverityLevel, string> = {
  stable: "bg-emerald-100 text-emerald-700",
  monitor: "bg-amber-100 text-amber-700",
  retrain: "bg-red-100 text-red-700",
};

function getSeverityLevel(psi: number | null | undefined): SeverityLevel {
  if (psi == null) return "stable";
  if (psi < 0.1) return "stable";
  if (psi < 0.25) return "monitor";
  return "retrain";
}

export function DriftExplainabilityCard({ driftSummary, psiReferences, monitoringNotes }: DriftExplainabilityCardProps) {
  const { t } = useI18n();

  const hasDrift = driftSummary && Object.keys(driftSummary).length > 0;
  const hasPsi = psiReferences && Object.keys(psiReferences).length > 0;

  const severityCounts = { stable: 0, monitor: 0, retrain: 0 };
  const psiEntries: { feature: string; psi: number | null }[] = hasPsi
    ? Object.entries(psiReferences!).map(([k, v]) => {
        const psi = typeof v === "number" ? v : null;
        const level = getSeverityLevel(psi);
        severityCounts[level]++;
        return { feature: k, psi };
      })
    : [];

  return (
    <Card>
      <CardTitle>{t("health.drift.title")}</CardTitle>
      <p className="mt-1 text-xs text-slate-400">{t("health.drift.subtitle")}</p>
      <p className="mt-1.5 text-xs leading-relaxed text-slate-500">{t("health.drift.psiExplanation")}</p>

      {psiEntries.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-3">
          {(Object.keys(severityCounts) as SeverityLevel[]).map((level) =>
            severityCounts[level] > 0 ? (
              <SeverityBadge
                key={level}
                count={severityCounts[level]}
                label={t(DRIFT_LABEL_KEYS[level])}
                color={DRIFT_COLORS[level]}
              />
            ) : null
          )}
        </div>
      )}

      {psiEntries.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr>
                <th className="px-2 py-1.5 font-medium">{t("health.drift.feature")}</th>
                <th className="px-2 py-1.5 font-medium">{t("health.drift.psi")}</th>
                <th className="px-2 py-1.5 font-medium">{t("health.drift.status")}</th>
                <th className="px-2 py-1.5 font-medium">{t("health.drift.interpretation")}</th>
              </tr>
            </thead>
            <tbody>
              {psiEntries.map((entry) => {
                const level = getSeverityLevel(entry.psi);
                return (
                  <tr key={entry.feature} className="border-t">
                    <td className="px-2 py-1.5 font-mono text-xs text-slate-600">{entry.feature}</td>
                    <td className="px-2 py-1.5 font-mono text-xs text-slate-600">{entry.psi != null ? entry.psi.toFixed(4) : "—"}</td>
                    <td className="px-2 py-1.5">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${DRIFT_COLORS[level]}`}>
                        {entry.psi != null ? t(DRIFT_LABEL_KEYS[level]) : t("health.drift.unknown")}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 text-xs text-slate-500 max-w-[200px]">
                      {entry.psi != null && entry.psi < 0.1 && t("health.drift.interpretStable")}
                      {entry.psi != null && entry.psi >= 0.1 && entry.psi < 0.25 && t("health.drift.interpretMonitor")}
                      {entry.psi != null && entry.psi >= 0.25 && t("health.drift.interpretRetrain")}
                      {entry.psi == null && "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {monitoringNotes.length > 0 && (
        <div className="mt-4 rounded-lg border border-amber-100 bg-amber-50 px-3 py-2">
          <p className="text-xs font-medium text-amber-700">{t("health.monitoringNotes")}</p>
          <ul className="mt-1 space-y-0.5">
            {monitoringNotes.map((note, i) => (
              <li key={i} className="flex gap-1.5 text-xs text-amber-600">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-amber-400" />
                <span>{note}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!hasDrift && !hasPsi && monitoringNotes.length === 0 && (
        <p className="mt-3 text-xs text-slate-400">{t("health.drift.noData")}</p>
      )}
    </Card>
  );
}

function SeverityBadge({ count, label, color }: { count: number; label: string; color: string }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${color}`}>
      {count} {label}
    </span>
  );
}