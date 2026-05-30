/**
 * Locale-Aware Formatting Utilities
 *
 * Provides locale-sensitive number, percentage, and decimal formatting for
 * the bilingual (English/Persian) UI. The Persian locale uses native digits
 * (۰-۹) for all numeric output while the locale-aware helper functions
 * preserve the correct digit system for each locale.
 *
 * Key design decisions:
 * - Persian digits are mapped via a lookup table for simple substitution
 *   (toLocaleString with "fa-IR" handles grouping but uses extended digits;
 *    we override with standard Persian digits for consistency)
 * - All functions return "—" (em dash) for null/undefined inputs to
 *   maintain a consistent empty-state convention across the app
 * - Percentage formatting multiplies by 100 internally (callers pass 0-1 ratio)
 */

const PERSIAN_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];

/**
 * Converts Western Arabic digits (0-9) to Persian digits (۰-۹).
 * Non-digit characters are passed through unchanged.
 */
export function toPersianDigits(num: string | number): string {
  return String(num).replace(/[0-9]/g, (d) => PERSIAN_DIGITS[parseInt(d, 10)]);
}

/**
 * Formats a 0-1 ratio as a percentage string.
 * E.g. 0.073 → "7.3%" (en) or "۷.۳%" (fa).
 * Returns "—" for null/undefined values.
 */
export function formatPercent(value: number | null | undefined, locale: string): string {
  if (value == null) return "—";
  const formatted = (value * 100).toFixed(1);
  if (locale === "fa") return `${toPersianDigits(formatted)}%`;
  return `${formatted}%`;
}

/**
 * Formats a number with locale-aware digit grouping.
 * E.g. 1234567 → "1,234,567" (en) or "۱٬۲۳۴٬۵۶۷" (fa).
 * Returns "—" for null/undefined values.
 */
export function formatNumber(value: number | null | undefined, locale: string): string {
  if (value == null) return "—";
  const formatted = value.toLocaleString(locale === "fa" ? "fa-IR" : "en-US");
  if (locale === "fa") return toPersianDigits(formatted);
  return formatted;
}

/**
 * Formats a decimal number to a fixed number of decimal places.
 * The default of 3 digits matches the standard precision for
 * ML metrics (precision, recall, F1) displayed in the UI.
 * Returns "—" for null/undefined values.
 */
export function formatDecimal(value: number | null | undefined, locale: string, digits = 3): string {
  if (value == null) return "—";
  const formatted = value.toFixed(digits);
  if (locale === "fa") return toPersianDigits(formatted);
  return formatted;
}
