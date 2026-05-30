/**
 * General-purpose utility helpers.
 *
 * Currently provides `cn()` for merging Tailwind CSS class names with
 * proper conflict resolution via `tailwind-merge`. This is the standard
 * pattern used across the codebase for conditional class composition.
 */

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merges Tailwind CSS class names with proper conflict resolution.
 * Combines clsx (conditional class logic) with tailwind-merge
 * (last-class-wins for conflicting Tailwind utilities).
 * This prevents bugs caused by additive class strings like "px-4 px-2".
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
