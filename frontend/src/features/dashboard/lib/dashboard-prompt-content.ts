import type { PromptChainDialogEntry } from "@/components";

function parseJson(value: string | null | undefined): unknown {
  if (!value) return null;

  try {
    return JSON.parse(value) as unknown;
  } catch {
    return value;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringifyContent(value: unknown): string {
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (
      (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
      (trimmed.startsWith("[") && trimmed.endsWith("]"))
    ) {
      try {
        return JSON.stringify(JSON.parse(trimmed), null, 2);
      } catch {
        return value;
      }
    }
    return value;
  }
  if (value === null || value === undefined) return "";
  return JSON.stringify(value, null, 2);
}

function getImageDataUrl(block: Record<string, unknown>): string | null {
  if (block.type === "image") {
    const base64 = block.base64;
    const mimeType = block.mime_type;
    if (
      typeof base64 === "string" &&
      typeof mimeType === "string" &&
      mimeType.startsWith("image/")
    ) {
      return `data:${mimeType};base64,${base64}`;
    }
  }

  if (block.type === "image_url" && isRecord(block.image_url)) {
    const url = block.image_url.url;
    if (typeof url === "string" && url.startsWith("data:image/")) return url;
  }

  return null;
}

function getMultimodalContent(
  content: unknown[],
): Pick<PromptChainDialogEntry, "content" | "imageUrls"> {
  const textParts: string[] = [];
  const imageUrls: string[] = [];

  for (const part of content) {
    if (!isRecord(part)) {
      textParts.push(stringifyContent(part));
      continue;
    }

    if (part.type === "text" && typeof part.text === "string") {
      textParts.push(part.text);
      continue;
    }

    const imageUrl = getImageDataUrl(part);
    if (imageUrl) {
      imageUrls.push(imageUrl);
      continue;
    }

    textParts.push(stringifyContent(part));
  }

  return { content: textParts.join("\n"), imageUrls };
}

export function getPromptEntries(
  requestMessages: string | null | undefined,
): PromptChainDialogEntry[] {
  const parsed = parseJson(requestMessages);
  if (!Array.isArray(parsed)) return [];

  return parsed.map((item, index) => {
    if (!isRecord(item)) {
      return {
        role: "unknown",
        content: stringifyContent(item),
        name: `#${index + 1}`,
      };
    }

    const multimodalContent = Array.isArray(item.content)
      ? getMultimodalContent(item.content)
      : { content: stringifyContent(item.content), imageUrls: [] };
    const toolCalls =
      Array.isArray(item.tool_calls) && item.tool_calls.length > 0
        ? `\n\nTool calls:\n${JSON.stringify(item.tool_calls, null, 2)}`
        : "";

    return {
      role: typeof item.role === "string" ? item.role : "unknown",
      content: `${multimodalContent.content}${toolCalls}`,
      imageUrls: multimodalContent.imageUrls,
      name: `#${index + 1}`,
    };
  });
}
