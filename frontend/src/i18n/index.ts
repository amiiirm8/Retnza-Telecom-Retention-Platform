export type Locale = "en" | "fa";

export type Dir = "ltr" | "rtl";

export const LOCALE_DIR: Record<Locale, Dir> = {
  en: "ltr",
  fa: "rtl",
};

export const LOCALE_LABEL: Record<Locale, string> = {
  en: "English",
  fa: "فارسی",
};

export const STORAGE_KEY = "retnza_locale";
