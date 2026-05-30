"use client";

import { useI18n } from "@/i18n/provider";
import { LOCALE_LABEL } from "@/i18n";
import type { Locale } from "@/i18n";
import { Globe } from "lucide-react";

export function LanguageSwitcher() {
  const { locale, setLocale } = useI18n();

  function toggle() {
    const next: Locale = locale === "en" ? "fa" : "en";
    setLocale(next);
  }

  return (
    <button
      onClick={toggle}
      className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
      title={locale === "en" ? "Switch to فارسی" : "Switch to English"}
    >
      <Globe size={16} />
      <span>{LOCALE_LABEL[locale]}</span>
    </button>
  );
}
