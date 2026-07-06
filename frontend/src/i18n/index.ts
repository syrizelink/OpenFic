/**
 * i18n Module
 *
 * 国际化配置和资源加载。
 * 语言偏好存储到 Dexie (IndexedDB) 和 localStorage（双写保证兼容性）。
 */

import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import { getPreference, setPreference } from "../lib/local-db";
import en from "./locales/en.json";
import zhCN from "./locales/zh-CN.json";

/** 支持的语言列表 */
export const supportedLanguages = [
  { code: "zh-CN", name: "简体中文" },
  { code: "en", name: "English" },
] as const;

export type LanguageCode = (typeof supportedLanguages)[number]["code"];

/** 默认语言 */
export const defaultLanguage: LanguageCode = "zh-CN";

/** 存储键 */
const LANGUAGE_STORAGE_KEY = "openfic-language";

/**
 * 获取初始语言（同步，用于 i18n 初始化）
 * 优先使用 localStorage 存储的语言，否则使用默认语言
 */
function getInitialLanguage(): LanguageCode {
  // i18n 初始化需要同步获取，因此使用 localStorage
  const storedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY);
  if (storedLanguage && supportedLanguages.some((lang) => lang.code === storedLanguage)) {
    return storedLanguage as LanguageCode;
  }
  return defaultLanguage;
}

/**
 * 保存语言偏好（双写到 Dexie 和 localStorage）
 */
export function saveLanguagePreference(language: LanguageCode): void {
  // 同步写入 localStorage（备份，用于下次同步读取）
  localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  // 异步写入 Dexie
  setPreference(LANGUAGE_STORAGE_KEY, language);
}

/**
 * 从 Dexie 加载语言偏好并同步到 i18n（应用启动后调用）
 */
export async function loadLanguagePreference(): Promise<void> {
  const saved = await getPreference(LANGUAGE_STORAGE_KEY);
  if (saved && supportedLanguages.some((lang) => lang.code === saved)) {
    if (i18n.language !== saved) {
      await i18n.changeLanguage(saved);
    }
    // 同步到 localStorage
    localStorage.setItem(LANGUAGE_STORAGE_KEY, saved);
  }
}

/** 翻译资源 */
const resources = {
  "zh-CN": { translation: zhCN },
  en: { translation: en },
};

i18n.use(initReactI18next).init({
  resources,
  lng: getInitialLanguage(),
  fallbackLng: defaultLanguage,
  interpolation: {
    escapeValue: false, // React 已经默认转义
  },
});

export default i18n;
