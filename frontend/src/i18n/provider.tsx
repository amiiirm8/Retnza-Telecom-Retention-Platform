"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import type { Locale, Dir } from "./index";
import { LOCALE_DIR, STORAGE_KEY } from "./index";
import en from "./en.json";
import fa from "./fa.json";

type TranslationValue = string | Record<string, unknown>;

interface I18nState {
  locale: Locale;
  dir: Dir;
  t: (key: string, params?: Record<string, string | number>) => string;
  setLocale: (locale: Locale) => void;
}

const dictionaries: Record<Locale, Record<string, TranslationValue>> = { en, fa };

function resolve(obj: Record<string, TranslationValue> | TranslationValue, path: string): string {
  const keys = path.split(".");
  let current: TranslationValue = obj;
  for (const key of keys) {
    if (typeof current === "object" && current !== null && key in current) {
      current = (current as Record<string, TranslationValue>)[key];
    } else {
      return path;
    }
  }
  return typeof current === "string" ? current : path;
}

function interpolate(text: string, params?: Record<string, string | number>): string {
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (_, key) => {
    const val = params[key];
    return val != null ? String(val) : `{${key}}`;
  });
}

export const I18nContext = createContext<I18nState | undefined>(undefined);

function getInitialLocale(): Locale {
  if (typeof window === "undefined") return "en";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "en" || stored === "fa") return stored;
  const navLang = navigator.language?.startsWith("fa") ? "fa" : "en";
  return navLang;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    setLocaleState(getInitialLocale());
  }, []);

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, newLocale);
    }
  }, []);

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => {
      const text = resolve(dictionaries[locale], key);
      return interpolate(text, params);
    },
    [locale]
  );

  const dir = LOCALE_DIR[locale];

  useEffect(() => {
    document.documentElement.dir = dir;
    document.documentElement.lang = locale;
  }, [dir, locale]);

  return (
    <I18nContext.Provider value={{ locale, dir, t, setLocale }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
