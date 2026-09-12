import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import id from "./locales/id.json";
import zhCN from "./locales/zh-CN.json";

export type DesktopLanguage = "id" | "en" | "zh-CN";

export function isDesktopLanguage(value: unknown): value is DesktopLanguage {
  return value === "id" || value === "en" || value === "zh-CN";
}

i18n.use(initReactI18next).init({
  resources: {
    id: { translation: { desktop: id } },
    en: { translation: { desktop: en } },
    "zh-CN": { translation: { desktop: zhCN } },
  },
  lng: "id",
  fallbackLng: "id",
  interpolation: {
    escapeValue: false,
  },
});

/**
 * Menyinkronkan atribut `lang` pada elemen <html> dengan bahasa i18n yang aktif.
 *
 * Listener terpusat agar penggantian bahasa dari mana pun ikut tersinkron.
 */
function syncDocumentLanguage(language: string): void {
  if (typeof document === "undefined") {
    return;
  }
  document.documentElement.lang = language;
}

syncDocumentLanguage(i18n.language ?? "id");
i18n.on("languageChanged", syncDocumentLanguage);

export default i18n;
