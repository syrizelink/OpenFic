/**
 * i18n Module
 *
 * Konfigurasi internasionalisasi dan pemuatan sumber daya.
 * Preferensi bahasa disimpan ke Dexie (IndexedDB) dan localStorage (tulis ganda untuk menjaga kompatibilitas).
 */

import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import { getPreference, setPreference } from "../lib/local-db";
import en from "./locales/en.json";
import id from "./locales/id.json";
import zhCN from "./locales/zh-CN.json";

/** Daftar bahasa yang didukung */
export const supportedLanguages = [
  { code: "id", name: "Bahasa Indonesia" },
  { code: "en", name: "English" },
  { code: "zh-CN", name: "\u7b80\u4f53\u4e2d\u6587" },
] as const;

export type LanguageCode = (typeof supportedLanguages)[number]["code"];

/** Bahasa bawaan */
export const defaultLanguage: LanguageCode = "id";

/** Kunci penyimpanan */
const LANGUAGE_STORAGE_KEY = "openfic-language";

/**
 * Mengambil bahasa awal (sinkron, dipakai untuk inisialisasi i18n)
 * Bahasa yang tersimpan di localStorage diutamakan, jika tidak ada maka bahasa bawaan dipakai
 */
function getInitialLanguage(): LanguageCode {
  // Inisialisasi i18n perlu pengambilan sinkron, jadi localStorage yang dipakai
  const storedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY);
  if (storedLanguage && supportedLanguages.some((lang) => lang.code === storedLanguage)) {
    return storedLanguage as LanguageCode;
  }
  return defaultLanguage;
}

/**
 * Menyimpan preferensi bahasa (tulis ganda ke Dexie dan localStorage)
 */
export function saveLanguagePreference(language: LanguageCode): void {
  // Menulis ke localStorage secara sinkron (cadangan, dipakai untuk pembacaan sinkron berikutnya)
  localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  // Menulis ke Dexie secara asinkron
  setPreference(LANGUAGE_STORAGE_KEY, language);
}

/**
 * Memuat preferensi bahasa dari Dexie dan menyinkronkannya ke i18n (dipanggil setelah aplikasi mulai)
 */
export async function loadLanguagePreference(): Promise<void> {
  const saved = await getPreference(LANGUAGE_STORAGE_KEY);
  if (saved && supportedLanguages.some((lang) => lang.code === saved)) {
    if (i18n.language !== saved) {
      await i18n.changeLanguage(saved);
    }
    // Menyinkronkan ke localStorage
    localStorage.setItem(LANGUAGE_STORAGE_KEY, saved);
  }
}

/** Sumber daya terjemahan */
const resources = {
  id: { translation: id },
  en: { translation: en },
  "zh-CN": { translation: zhCN },
};

i18n.use(initReactI18next).init({
  resources,
  lng: getInitialLanguage(),
  fallbackLng: defaultLanguage,
  interpolation: {
    escapeValue: false, // React sudah meng-escape secara bawaan
  },
});

/**
 * Menyinkronkan atribut `lang` pada elemen <html> dengan bahasa i18n yang aktif.
 *
 * Dipasang sebagai listener terpusat, bukan di setiap pemanggil `changeLanguage`,
 * sehingga semua jalur penggantian bahasa (pengaturan, sidebar, pemuatan preferensi)
 * ikut tersinkron tanpa perlu penyesuaian tambahan.
 */
function syncDocumentLanguage(language: string): void {
  if (typeof document === "undefined") {
    return;
  }
  document.documentElement.lang = language;
}

syncDocumentLanguage(i18n.language ?? defaultLanguage);
i18n.on("languageChanged", syncDocumentLanguage);

export default i18n;
