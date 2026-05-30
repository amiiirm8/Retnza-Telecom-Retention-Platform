/**
 * Governance Metric Formatting Utilities (deprecated — use format.ts instead)
 *
 * These formatters are preserved for backward compatibility but new code
 * should prefer the locale-aware helpers in lib/format.ts.
 *
 * @deprecated Use format.ts functions (formatDecimal, formatNumber, formatPercent)
 *             which support Persian digits and locale-aware output.
 */

/**
 * Formats a numeric metric value to a fixed number of decimal places.
 * Retained from the original governance UI; superseded by locale-aware helpers.
 * @deprecated Use formatDecimal(value, locale, decimals) from format.ts
 */
export function formatMetric(value: number | null | undefined, decimals = 3): string {
  if (value == null) return "—";
  return value.toFixed(decimals);
}

/**
 * Formats a threshold value to 4 decimal places — the standard precision
 * used for model operating thresholds across the governance dashboard.
 * @deprecated Use formatDecimal(value, locale, 4) from format.ts
 */
export function formatThreshold(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toFixed(4);
}

/**
 * Formats an ISO timestamp to a locale-aware date/time string.
 * Handles Persian (fa-IR) locale by using Latin numerals (fa-IR-u-nu-latn)
 * to avoid mixing digit systems in numeric contexts.
 * @deprecated Use format functions from format.ts; this is kept for legacy locale awareness
 */
export function formatTimestamp(iso: string | null | undefined, locale: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(locale === "fa" ? "fa-IR-u-nu-latn" : "en-US");
  } catch {
    return iso;
  }
}

/** Formats an ISO timestamp as a compact relative-time string. */
export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const now = Date.now();
  const updated = new Date(iso).getTime();
  if (isNaN(updated)) return iso;
  const diffMs = now - updated;
  const minutes = Math.floor(diffMs / (1000 * 60));
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (minutes < 1) return "moments ago";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

/** Formats an ISO timestamp as a human-readable freshness description. */
export function formatFreshnessDescription(iso: string | null | undefined): string {
  if (!iso) return "Unknown";
  const now = Date.now();
  const updated = new Date(iso).getTime();
  if (isNaN(updated)) return iso;
  const diffMs = now - updated;
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (hours < 1) return "Updated moments ago";
  if (hours < 24) return `Updated ${hours}h ago`;
  if (days === 1) return "Updated yesterday";
  if (days < 30) return `Updated ${days}d ago`;
  if (days < 365) return `Updated ${Math.floor(days / 30)}mo ago`;
  return `Updated ${Math.floor(days / 365)}y ago`;
}
