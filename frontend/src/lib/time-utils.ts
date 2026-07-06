/**
 * Time Utils
 *
 * 时间相关的工具函数。
 */

import { formatDistanceToNow, differenceInMinutes, parseISO } from "date-fns";
import { zhCN, enUS } from "date-fns/locale";

import i18n from "@/i18n";

/**
 * 解析 ISO 时间字符串，处理时区问题
 * 如果时间字符串没有时区信息，将其当作 UTC 时间
 */
function parseDate(dateString: string): Date {
  // 如果没有时区信息（没有 Z 或 +/- 时区偏移），添加 Z 表示 UTC
  if (!dateString.endsWith("Z") && !dateString.match(/[+-]\d{2}:\d{2}$/)) {
    return parseISO(dateString + "Z");
  }
  return parseISO(dateString);
}

/**
 * 根据当前语言获取 date-fns locale
 */
function getDateLocale() {
  const language = i18n.language;
  switch (language) {
    case "zh-CN":
      return zhCN;
    case "en":
      return enUS;
    default:
      return zhCN;
  }
}

/**
 * 格式化相对时间
 * 5 分钟内显示"片刻之前"，否则显示相对时间
 */
export function formatRelativeTime(dateString: string): string {
  const date = parseDate(dateString);
  const now = new Date();
  const diffMinutes = differenceInMinutes(now, date);

  if (diffMinutes < 5) {
    return i18n.t("time.justNow");
  }

  return formatDistanceToNow(date, {
    addSuffix: true,
    locale: getDateLocale(),
  });
}
