/**
 * UI Scale Utils
 *
 * 界面缩放：以百分比缩放整个应用界面（含字体），
 * 用于高分屏下增大文字与控件尺寸。
 */

export const UI_SCALE_OPTIONS = [75, 90, 100, 110, 125, 150] as const;

export const DEFAULT_UI_SCALE = 100;

export const MIN_UI_SCALE = 50;
export const MAX_UI_SCALE = 200;

export function normalizeUiScale(value: unknown): number {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) return DEFAULT_UI_SCALE;
  return Math.min(MAX_UI_SCALE, Math.max(MIN_UI_SCALE, Math.round(parsed)));
}

/** 将界面缩放应用到文档根元素。 */
export function applyUiScale(scale: number): void {
  const normalized = normalizeUiScale(scale);
  const root = document.documentElement;
  if (normalized === DEFAULT_UI_SCALE) {
    root.style.removeProperty("zoom");
    return;
  }
  root.style.setProperty("zoom", `${normalized}%`);
}
