/**
 * Font Utilities
 *
 * Fungsi bantu penerapan fon
 */

import {
  SYSTEM_CODE_FONT_FAMILY,
  SYSTEM_FONT_FAMILY,
} from "@/features/settings/lib/settings.types";

import { publishDesktopAppearance } from "./desktop-appearance-bridge";

const appFontFallbacks =
  '"Noto Serif SC Variable", "Noto Sans SC Variable", Georgia, "PingFang SC", "Microsoft YaHei", serif';
const codeFontFallbacks =
  '"JetBrains Mono Variable", ui-monospace, "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace';

/** Ukuran fon dasar bawaan (px), selaras dengan --font-size-base di tokens.css. */
export const DEFAULT_BASE_FONT_SIZE = 14;

/** Ukuran fon editor bawaan (px), selaras dengan --font-size-editor di tokens.css. */
export const DEFAULT_EDITOR_FONT_SIZE = 16;

const FONT_SIZE_SCALE = {
  xs: 11,
  sm: 12,
  md: 13,
  base: 14,
  lg: 15,
  xl: 16,
  "2xl": 24,
  "3xl": 28,
} as const;
const FONT_SIZE_STEPS = Object.keys(FONT_SIZE_SCALE) as Array<keyof typeof FONT_SIZE_SCALE>;

/** Nilai acuan variabel ukuran fon komponen Radix Themes (--font-size-1..9) pada skala bawaan (--scaling: 1). */
const RADIX_FONT_SIZE_DEFAULTS = {
  "1": 12,
  "2": 14,
  "3": 16,
  "4": 18,
  "5": 20,
  "6": 24,
  "7": 28,
  "8": 35,
  "9": 60,
} as const;
const RADIX_FONT_SIZE_STEPS = Object.keys(RADIX_FONT_SIZE_DEFAULTS) as Array<
  keyof typeof RADIX_FONT_SIZE_DEFAULTS
>;

const FONT_SIZE_STYLE_ID = "openfic-base-font-size";

/**
 * Menerapkan ukuran fon dasar kustom (px) ke halaman.
 *
 * Ukuran fon dasar bawaan dipakai sebagai jangkar, lalu seluruh variabel --font-size-*
 * diskalakan proporsional mengikuti ukuran fon dasar pilihan pengguna. Gaya global juga
 * disuntikkan untuk menimpa --font-size-1..9 milik Radix Themes agar komponennya
 * (termasuk dialog/dropdown yang dirender lewat portal) ikut terskala; penimpaan dibersihkan saat setelan sama dengan nilai bawaan.
 */
export function applyBaseFontSize(baseFontSize: number): void {
  const scale = baseFontSize / DEFAULT_BASE_FONT_SIZE;
  const root = document.documentElement;

  if (scale !== 1) {
    for (const step of FONT_SIZE_STEPS) {
      root.style.setProperty(`--font-size-${step}`, `${FONT_SIZE_SCALE[step] * scale}px`);
    }
  } else {
    for (const step of FONT_SIZE_STEPS) {
      root.style.removeProperty(`--font-size-${step}`);
    }
  }

  const existing = document.getElementById(FONT_SIZE_STYLE_ID);
  if (scale === 1) {
    existing?.remove();
    return;
  }

  const rules = RADIX_FONT_SIZE_STEPS.map(
    (step) => `--font-size-${step}: ${RADIX_FONT_SIZE_DEFAULTS[step] * scale}px;`,
  ).join(" ");
  const style = existing ?? document.createElement("style");
  style.id = FONT_SIZE_STYLE_ID;
  style.textContent = `.radix-themes { ${rules} }`;
  if (!existing) document.head.appendChild(style);
}

/**
 * Menerapkan ukuran fon editor kustom (px) ke halaman.
 *
 * Variabel --font-size-editor disetel langsung untuk mengatur ukuran fon isi utama/editor;
 * penimpaan dibersihkan saat setelan sama dengan nilai bawaan, kembali ke nilai bawaan tokens.css.
 * @param editorFontSize Ukuran fon editor pilihan pengguna (px)
 */
export function applyEditorFontSize(editorFontSize: number): void {
  const root = document.documentElement;
  if (editorFontSize === DEFAULT_EDITOR_FONT_SIZE) {
    root.style.removeProperty("--font-size-editor");
    return;
  }
  root.style.setProperty("--font-size-editor", `${editorFontSize}px`);
}

function buildFontStack(fontFamily: string, systemFontFamily: string, fallbacks: string): string {
  if (fontFamily === systemFontFamily) return `${systemFontFamily}, ${fallbacks}`;
  return `"${fontFamily}", ${fallbacks}`;
}

/**
 * Menerapkan fon ke halaman
 * @param fontFamily Nama keluarga fon
 */
export function applyFontFamily(fontFamily: string): void {
  // Membangun tumpukan fon lengkap
  const fontStack = buildFontStack(fontFamily, SYSTEM_FONT_FAMILY, appFontFallbacks);

  // Menerapkan ke elemen akar dokumen
  document.documentElement.style.fontFamily = fontStack;
  document.documentElement.style.setProperty("--app-font-family", fontStack);

  // Sekaligus memperbarui variabel fon radix-themes
  const radixThemesEl = document.querySelector(".radix-themes");
  if (radixThemesEl instanceof HTMLElement) {
    radixThemesEl.style.setProperty("--default-font-family", fontStack);
  }

  publishDesktopAppearance({ fontFamily: fontStack });
}

/**
 * Menerapkan fon kode ke halaman
 * @param codeFontFamily Nama keluarga fon kode
 */
export function applyCodeFontFamily(codeFontFamily: string): void {
  // Membangun tumpukan fon kode lengkap
  const fontStack = buildFontStack(codeFontFamily, SYSTEM_CODE_FONT_FAMILY, codeFontFallbacks);

  // Memperbarui variabel CSS
  const radixThemesEl = document.querySelector(".radix-themes");
  if (radixThemesEl instanceof HTMLElement) {
    radixThemesEl.style.setProperty("--code-font-family", fontStack);
  }

  // Menerapkan ke seluruh elemen terkait kode
  document.documentElement.style.setProperty("--code-font-family", fontStack);

  publishDesktopAppearance({ codeFontFamily: fontStack });
}

export async function loadConfiguredFonts(
  fontFamily: string,
  codeFontFamily: string,
): Promise<void> {
  if (!("fonts" in document)) return;

  const configuredFonts = [fontFamily, codeFontFamily].filter(
    (font) => font !== SYSTEM_FONT_FAMILY && font !== SYSTEM_CODE_FONT_FAMILY,
  );
  if (!configuredFonts.length) return;

  await Promise.all(configuredFonts.map((font) => document.fonts.load(`1em "${font}"`)));
  await document.fonts.ready;
}
