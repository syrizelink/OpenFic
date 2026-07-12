/**
 * HTML Utils
 *
 * HTML 相关的工具函数。
 */

/**
 * 将 HTML 内容转换为换行符格式
 * 用于保存到数据库时，将 Tiptap 的 HTML 格式转换为纯文本换行符
 *
 * 处理逻辑：
 * 1. 将 </p> 替换为换行符
 * 2. 移除所有 HTML 标签
 * 3. 将 HTML 实体反转义（&lt; → <, &gt; → >, &amp; → &）
 *
 * @param html HTML 内容
 * @returns 纯文本内容，使用换行符分隔段落
 */
export function htmlToNewlines(html: string): string {
  if (!html) return "";

  let result = html;

  // 1. 将 </p> 替换为换行符
  result = result.replace(/<\/p\b>/gi, "\n");

  // 2. 移除 <p> 标签（包括带属性的）
  result = result.replace(/<p\b[^>]*>/gi, "");

  // 3. 移除其他所有 HTML 标签（如 <br> 等）
  result = result.replace(/<[^>]+>/g, "");

  // 4. 将 HTML 实体反转义
  result = decodeHtmlEntities(result);

  // 5. 移除开头和结尾的空白字符
  result = result.trim();

  return result;
}

/**
 * 将 HTML 实体反转义为原始字符
 */
function decodeHtmlEntities(text: string): string {
  return text
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&"); // &amp; 必须最后处理
}

/**
 * 将换行符格式的文本转换为 HTML
 * 用于从数据库加载时，将纯文本换行符转换为 Tiptap 可以显示的 HTML 格式
 *
 * 处理逻辑：
 * 1. 对文本进行 HTML 转义
 * 2. 按换行符分割段落，每段用 <p></p> 包裹
 *
 * @param text 纯文本内容，使用换行符分隔段落
 * @returns HTML 内容，包含 <p></p> 段落标签
 */
export function newlinesToHtml(text: string): string {
  if (!text) return "";

  // 按换行分割成段落（保留空行）
  const paragraphs = text.split("\n");

  // 构建 HTML（保留空段落，转换为空的 <p></p> 标签）
  const htmlParts: string[] = [];
  for (const p of paragraphs) {
    if (!p.trim()) {
      // 空段落，保留为空的 <p></p> 标签以保持换行
      htmlParts.push("<p></p>");
    } else {
      htmlParts.push(`<p>${escapeHtml(p)}</p>`);
    }
  }

  return htmlParts.join("");
}

/**
 * HTML 转义（用于文本内容）
 */
function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
