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
  '"Noto Serif SC Variable", "Noto Sans SC Variable", Georgia, "PingFang SC", "Microsoft YaHei", serif';
const codeFontFallbacks =
  '"JetBrains Mono Variable", ui-monospace, "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace';

/** 默认基础字号（px），与 tokens.css 中的 --font-size-base 保持一致。 */
export const DEFAULT_BASE_FONT_SIZE = 14;

/** 默认编辑器字号（px），与 tokens.css 中的 --font-size-editor 保持一致。 */
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

/** Radix Themes 组件字号变量（--font-size-1..9）在默认缩放（--scaling: 1）下的基准值。 */
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
 * 应用自定义基础字号（px）到页面。
 *
 * 以默认基础字号为锚点，按用户设置的基础字号等比缩放整套 --font-size-* 变量，
 * 并通过注入全局样式覆盖 Radix Themes 的 --font-size-1..9，使其组件
 * （含 portal 渲染的对话框/下拉等）跟随缩放；当设置等于默认值时清除覆盖。
 * @param baseFontSize 用户设置的基础字号（px）
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
 * 应用自定义编辑器字号（px）到页面。
 *
 * 直接设置 --font-size-editor 变量控制正文/编辑器内容字号；
 * 当设置等于默认值时清除覆盖，回落到 tokens.css 的默认值。
 * @param editorFontSize 用户设置的编辑器字号（px）
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
