/**
 * Font Utilities
 *
 * 字体应用工具函数
 */

/**
 * 应用字体到页面
 * @param fontFamily 字体族名称
 */
export function applyFontFamily(fontFamily: string): void {
  // 构建完整的字体栈
  const fontStack = `"${fontFamily}", "SourceHanSerifCN-VF", "SourceHanSansCN-VF", "ChillKai", "Source Han Serif SC", "Noto Serif CJK SC", Georgia, "PingFang SC", "Microsoft YaHei", serif`;

  // 应用到文档根元素
  document.documentElement.style.fontFamily = fontStack;
  document.documentElement.style.setProperty("--app-font-family", fontStack);

  // 同时更新 radix-themes 的字体变量
  const radixThemesEl = document.querySelector(".radix-themes");
  if (radixThemesEl instanceof HTMLElement) {
    radixThemesEl.style.setProperty("--default-font-family", fontStack);
  }
}

/**
 * 应用代码字体到页面
 * @param codeFontFamily 代码字体族名称
 */
export function applyCodeFontFamily(codeFontFamily: string): void {
  // 构建完整的代码字体栈
  const fontStack = `"${codeFontFamily}", "JetBrainsMapleMono", ui-monospace, "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace`;

  // 更新 CSS 变量
  const radixThemesEl = document.querySelector(".radix-themes");
  if (radixThemesEl instanceof HTMLElement) {
    radixThemesEl.style.setProperty("--code-font-family", fontStack);
  }

  // 应用到所有代码相关的元素
  document.documentElement.style.setProperty("--code-font-family", fontStack);
}

export async function loadConfiguredFonts(
  fontFamily: string,
  codeFontFamily: string
): Promise<void> {
  if (!("fonts" in document)) return;

  await Promise.all([
    document.fonts.load(`1em "${fontFamily}"`),
    document.fonts.load(`1em "${codeFontFamily}"`),
  ]);
  await document.fonts.ready;
}
