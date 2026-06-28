/**
 * Pinyin Search Utils
 *
 * 拼音搜索工具函数，支持汉字转拼音和首字母提取。
 */

import Pinyin from "tiny-pinyin";

/**
 * 获取文本的完整拼音（小写，无空格）
 */
export function getPinyin(text: string): string {
  if (!text) return "";
  return Pinyin.convertToPinyin(text, "", true);
}

/**
 * 获取拼音首字母序列
 * 例如：第一章 -> dyz
 */
export function getInitials(text: string): string {
  if (!text) return "";
  const chars = text.split("");
  return chars
    .map((char) => {
      if (Pinyin.isSupported()) {
        const pinyinArr = Pinyin.parse(char);
        if (pinyinArr.length > 0 && pinyinArr[0].type === 2) {
          // type 2 表示汉字
          return pinyinArr[0].target.charAt(0).toLowerCase();
        }
      }
      // 非汉字直接返回原字符（如果是字母则小写）
      return char.toLowerCase();
    })
    .join("");
}

/**
 * 去除 HTML 标签，返回纯文本
 * 将换行标签（p, br）转换为空格，避免跨行匹配
 */
export function stripHtml(html: string): string {
  if (!html) return "";
  // 将换行相关标签替换为空格
  const processed = html
    .replace(/<\/p>/gi, " ")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<\/div>/gi, " ")
    .replace(/<\/li>/gi, " ");
  // 创建临时 DOM 元素来解析剩余 HTML
  const doc = new DOMParser().parseFromString(processed, "text/html");
  // 获取纯文本并压缩多余空格
  const text = doc.body.textContent || "";
  return text.replace(/\s+/g, " ").trim();
}

/**
 * 默认的 Fuse.js 搜索配置
 */
export const defaultFuseOptions = {
  includeMatches: true,
  threshold: 0.1,
  ignoreLocation: true,
  distance: 50,
  useExtendedSearch: false,
};

/**
 * 简单的拼音匹配函数
 * 支持：原文匹配、全拼匹配、首字母匹配
 */
export function pinyinMatch(text: string, query: string): boolean {
  if (!text || !query) return false;

  try {
    const lowerText = text.toLowerCase();
    const lowerQuery = query.toLowerCase();

    // 原文匹配
    if (lowerText.includes(lowerQuery)) {
      return true;
    }

    // 全拼匹配
    const pinyin = getPinyin(text);
    if (pinyin.includes(lowerQuery)) {
      return true;
    }

    // 首字母匹配
    const initials = getInitials(text);
    if (initials.includes(lowerQuery)) {
      return true;
    }

    return false;
  } catch {
    return text.toLowerCase().includes(query.toLowerCase());
  }
}
