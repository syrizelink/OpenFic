/**
 * HTML Utils
 *
 * HTML 相关的工具函数。
 */

/**
 * 将 HTML 内容（包含 <p></p> 标签和宏节点）转换为换行符格式
 * 用于保存到数据库时，将 Tiptap 的 HTML 格式转换为纯文本换行符
 *
 * 处理逻辑：
 * 1. 将宏节点的 span 标签还原为原始宏表达式（从 data-macro-raw 属性提取）
 * 2. 将 </p> 替换为换行符
 * 3. 移除所有 HTML 标签
 * 4. 将 HTML 实体反转义（&lt; → <, &gt; → >, &amp; → &）
 *
 * @param html HTML 内容（包含 <p></p> 标签和宏节点）
 * @returns 纯文本内容，使用换行符分隔段落，宏表达式为原始格式
 */
export function htmlToNewlines(html: string): string {
  if (!html) return "";

  let result = html;

  // 1. 将宏节点 span 标签还原为原始宏表达式
  // 匹配 <span data-macro-node="true" ... data-macro-raw="{{...}}" ...>...</span>
  // 或 <span ... macroraw="{{...}}" ...>...</span> (属性可能是小写)
  result = result.replace(
    /<span[^>]*data-macro-node="true"[^>]*>([^<]*)<\/span>/gi,
    (match, _content) => {
      // 从 span 标签中提取 macroRaw 属性
      const macroRawMatch = match.match(/macroraw="([^"]*)"/i);
      if (macroRawMatch) {
        // 解码 HTML 实体（属性值中可能包含转义的字符）
        return decodeHtmlEntities(macroRawMatch[1]);
      }
      // 如果没有 macroRaw 属性，使用 span 的文本内容
      return _content;
    },
  );

  // 2. 将 </p> 替换为换行符
  result = result.replace(/<\/p\b>/gi, "\n");

  // 3. 移除 <p> 标签（包括带属性的）
  result = result.replace(/<p\b[^>]*>/gi, "");

  // 4. 移除其他所有 HTML 标签（如 <br> 等）
  result = result.replace(/<[^>]+>/g, "");

  // 5. 将 HTML 实体反转义
  result = decodeHtmlEntities(result);

  // 6. 移除开头和结尾的空白字符
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
 * 将换行符格式的文本转换为 HTML（包含 <p></p> 标签和宏节点）
 * 用于从数据库加载时，将纯文本换行符转换为 Tiptap 可以显示的 HTML 格式
 *
 * 处理逻辑：
 * 1. 识别文本中的宏表达式（如 {{getmem::chapter::near}}）
 * 2. 将宏表达式转换为 Tiptap macroNode 的 HTML 格式
 * 3. 对非宏文本进行 HTML 转义
 * 4. 按换行符分割段落，每段用 <p></p> 包裹
 *
 * @param text 纯文本内容，使用换行符分隔段落，宏表达式为原始格式
 * @returns HTML 内容，包含 <p></p> 段落标签和 macroNode span 标签
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
      // 非空段落，处理宏表达式和 HTML 转义
      const processedContent = processLineWithMacros(p);
      htmlParts.push(`<p>${processedContent}</p>`);
    }
  }

  return htmlParts.join("");
}

import { tryParseMacro } from "./macro";

/**
 * 处理单行文本，识别宏表达式并转换为 macroNode HTML
 * 非宏部分进行 HTML 转义
 */
function processLineWithMacros(line: string): string {
  // 匹配宏表达式：{{...}}
  const macroPattern = /\{\{([^{}]+)\}\}/g;

  let result = "";
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = macroPattern.exec(line)) !== null) {
    // 添加宏之前的文本（HTML 转义）
    if (match.index > lastIndex) {
      const textBefore = line.slice(lastIndex, match.index);
      result += escapeHtml(textBefore);
    }

    const macroRaw = match[0];
    const macroBody = match[1].trim();

    // 尝试解析宏使用完整的解析器逻辑（包含合法性验证）
    // 为了利用 tryParseMacro，我们需要构造一个临时的 MacroMatch 对象
    const macroMatchKey = {
      body: macroBody,
      raw: macroRaw,
      start: match.index,
      end: match.index + macroRaw.length,
    };

    const macroNode = tryParseMacro(macroMatchKey);

    if (macroNode) {
      // 解析成功且合法，生成宏节点 HTML
      const macroName = macroNode.name;
      // 序列化 args
      const macroData = JSON.stringify({ args: macroNode.args });

      // 属性值需要 HTML 转义
      const escapedMacroRaw = escapeHtmlAttribute(macroRaw);
      const escapedMacroName = escapeHtmlAttribute(macroName);
      const escapedMacroData = escapeHtmlAttribute(macroData);

      result += `<span data-macro-node="true" macroname="${escapedMacroName}" macroraw="${escapedMacroRaw}" macrodata="${escapedMacroData}" class="macro-node macro-${escapedMacroName}">${escapeHtml(macroRaw)}</span>`;
    } else {
      // 解析失败或非法，作为普通文本处理
      result += escapeHtml(macroRaw);
    }

    lastIndex = match.index + match[0].length;
  }

  // 添加剩余的文本（HTML 转义）
  if (lastIndex < line.length) {
    result += escapeHtml(line.slice(lastIndex));
  }

  return result;
}

/**
 * HTML 转义（用于文本内容）
 */
function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * HTML 属性值转义
 */
function escapeHtmlAttribute(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
