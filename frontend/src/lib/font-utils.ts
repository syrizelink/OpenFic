/**
 * Font Utilities
 *
 * 字体应用工具函数
 */

import {
  SYSTEM_CODE_FONT_FAMILY,
  SYSTEM_FONT_FAMILY,
} from "@/features/settings/lib/settings.types";

import { publishDesktopAppearance } from "./desktop-appearance-bridge";

const appFontFallbacks =
  '"SourceHanSerifCN-VF", "SourceHanSansCN-VF", "ChillKai", "Source Han Serif SC", "Noto Serif CJK SC", Georgia, "PingFang SC", "Microsoft YaHei", serif';
const codeFontFallbacks =
  '"JetBrainsMapleMono", ui-monospace, "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace';

function buildFontStack(fontFamily: string, systemFontFamily: string, fallbacks: string): string {
  if (fontFamily === systemFontFamily) return `${systemFontFamily}, ${fallbacks}`;
  return `"${fontFamily}", ${fallbacks}`;
}

/**
 * 应用字体到页面
 * @param fontFamily 字体族名称
 */
export function applyFontFamily(fontFamily: string): void {
  // 构建完整的字体栈
  const fontStack = buildFontStack(fontFamily, SYSTEM_FONT_FAMILY, appFontFallbacks);

  // 应用到文档根元素
  document.documentElement.style.fontFamily = fontStack;
  document.documentElement.style.setProperty("--app-font-family", fontStack);

  // 同时更新 radix-themes 的字体变量
  const radixThemesEl = document.querySelector(".radix-themes");
  if (radixThemesEl instanceof HTMLElement) {
    radixThemesEl.style.setProperty("--default-font-family", fontStack);
  }

  publishDesktopAppearance({ fontFamily: fontStack });
}

/**
 * 应用代码字体到页面
 * @param codeFontFamily 代码字体族名称
 */
export function applyCodeFontFamily(codeFontFamily: string): void {
  // 构建完整的代码字体栈
  const fontStack = buildFontStack(codeFontFamily, SYSTEM_CODE_FONT_FAMILY, codeFontFallbacks);

  // 更新 CSS 变量
  const radixThemesEl = document.querySelector(".radix-themes");
  if (radixThemesEl instanceof HTMLElement) {
    radixThemesEl.style.setProperty("--code-font-family", fontStack);
  }

  // 应用到所有代码相关的元素
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
