import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import zhCN from "./locales/zh-CN.json";

export type DesktopLanguage = "zh-CN" | "en";

export function isDesktopLanguage(value: unknown): value is DesktopLanguage {
  return value === "zh-CN" || value === "en";
}

i18n.use(initReactI18next).init({
  resources: {
    "zh-CN": { translation: { desktop: zhCN } },
    en: { translation: { desktop: en } },
  },
  lng: "zh-CN",
  fallbackLng: "zh-CN",
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;
