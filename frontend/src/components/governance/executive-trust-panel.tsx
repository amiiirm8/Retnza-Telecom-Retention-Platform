/**
 * Executive Trust Panel
 *
 * Displays 10 safeguards built into the retention AI platform that executives
 * can rely on for production decisioning:
 *
 * 1. Calibrated Probabilities — reliable risk scores
 * 2. Explainability Enabled — SHAP + rule-based driver analysis
 * 3. Governance Alignment — schema compatibility, artifact freshness validation
 * 4. Schema Validation — versioned data pipeline contracts
 * 5. Drift Monitoring — PSI-based population stability tracking
 * 6. SHAP Explainability — per-customer driver identification
 * 7. Full Audit Trail — versioned, timestamped artifact tracking
 * 8. Deterministic Recommendation Engine — rules-based, not ML-driven
 * 9. Telecom-Specific Design — purpose-built for telecom CRM
 * 10. Business Labels Throughout — every metric has plain-English interpretation
 */

import { Card, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n/provider";

const TRUST_FACTORS = [
  { key: "calibrated", icon: "✓" },
  { key: "explainability", icon: "✓" },
  { key: "governance", icon: "✓" },
  { key: "schemaValidation", icon: "✓" },
  { key: "driftMonitoring", icon: "✓" },
  { key: "shap", icon: "✓" },
  { key: "auditability", icon: "✓" },
  { key: "deterministic", icon: "✓" },
  { key: "telecomSpecific", icon: "✓" },
  { key: "businessLabels", icon: "✓" },
];

export function ExecutiveTrustPanel() {
  const { t } = useI18n();

  return (
    <Card>
      <CardTitle>{t("governance.trust.title")}</CardTitle>
      <p className="mt-1 text-xs text-slate-400">{t("governance.trust.subtitle")}</p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {TRUST_FACTORS.map((factor) => {
          const info = t(`governance.trust.factors.${factor.key}`) as unknown as { label: string; description: string } | string;
          const label = typeof info === "string" ? factor.key : (info as { label: string }).label;
          const description = typeof info === "string" ? "" : (info as { label: string; description: string }).description;

          return (
            <div key={factor.key} className="flex gap-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2.5">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-[10px] text-emerald-700">
                {factor.icon}
              </span>
              <div>
                <p className="text-xs font-medium text-slate-700">{label}</p>
                {description && (
                  <p className="mt-0.5 text-[10px] text-slate-500 leading-relaxed">{description}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
