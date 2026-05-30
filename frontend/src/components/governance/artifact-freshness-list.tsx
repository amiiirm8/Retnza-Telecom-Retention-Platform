/**
 * Artifact Freshness List
 *
 * Displays the age and freshness status of all production artifacts (model,
 * recommendation manifest, SHAP manifest, feature manifest, calibration).
 * Each artifact shows:
 * - Human-readable name from the ARTIFACT_LABELS registry
 * - Relative time since last update
 * - Freshness badge (Fresh / Recent / Aging / Stale)
 * - Full timestamp on hover
 *
 * Stale artifacts are flagged with a governance warning since they may
 * reflect outdated model or configuration state.
 */

import { Card, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/provider";
import { getFreshnessLevel, FRESHNESS_COLORS, ARTIFACT_LABELS } from "@/lib/governance-labels";
import { formatFreshnessDescription, formatTimestamp } from "@/lib/governance-formatters";

interface ArtifactFreshnessListProps {
  artifacts: Record<string, string>;
  locale?: string;
}

export function ArtifactFreshnessList({ artifacts, locale }: ArtifactFreshnessListProps) {
  const { t } = useI18n();
  const entries = Object.entries(artifacts || {});

  if (entries.length === 0) return null;

  return (
    <Card>
      <CardTitle>{t("governance.freshness.title")}</CardTitle>
      <p className="mt-1 text-xs text-slate-400">{t("governance.freshness.explanation")}</p>
      <div className="mt-3 space-y-2">
        {entries.map(([key, ts]) => {
          const { level, label, hours } = getFreshnessLevel(ts);
          const artifactLabel = ARTIFACT_LABELS[key] || key.replace(/_/g, " ");
          const desc = formatFreshnessDescription(ts);
          const color = FRESHNESS_COLORS[level];
          const relativeTime = hours < Infinity
            ? hours < 1
              ? `<1h`
              : hours < 24
                ? `${Math.round(hours)}h`
                : `${Math.round(hours / 24)}d`
            : "";
          return (
            <div key={key} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-800">{artifactLabel}</p>
                <p className="text-xs text-slate-400">
                  {desc}
                  {relativeTime && <span className="ml-1 rtl:mr-1 text-slate-300">({relativeTime})</span>}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${color}`}
                  title={formatTimestamp(ts, locale ?? "en")}
                >
                  {label}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
