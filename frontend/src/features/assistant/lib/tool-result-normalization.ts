import i18n from "@/i18n";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

export function getString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function parseMaybeJson(value: unknown): unknown {
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

interface NormalizeToolResultOptions {
  status?: unknown;
  toolCallId?: unknown;
  toolName?: unknown;
  success?: unknown;
}

function normalizeParsedToolResult(
  parsed: unknown,
  options: NormalizeToolResultOptions = {}
): Record<string, unknown> {
  const status = getString(options.status);
  const isErrorStatus = status === "error";
  const toolCallId = getString(options.toolCallId);
  const toolName = getString(options.toolName);
  const explicitSuccess = typeof options.success === "boolean" ? options.success : undefined;

  if (isRecord(parsed)) {
    const errorText = getString(parsed.error);
    const messageText = getString(parsed.message) || errorText;
    const success =
      explicitSuccess
      ?? (typeof parsed.success === "boolean" ? parsed.success : !errorText && !isErrorStatus);
    return {
      ...parsed,
      type: parsed.type ?? (success ? "ok" : "fail"),
      success,
      reason: parsed.reason ?? (!success ? "tool_error" : undefined),
      message: messageText,
      data: parsed.data ?? (!success ? null : parsed),
      tool_call_id: parsed.tool_call_id ?? toolCallId,
      tool_name: parsed.tool_name ?? toolName,
    };
  }

  if (isErrorStatus || explicitSuccess === false) {
    const message = getString(parsed) || i18n.t("assistant.tools.toolError");
    return {
      type: "fail",
      success: false,
      recoverable: true,
      reason: "tool_error",
      message,
      data: null,
      tool_call_id: toolCallId,
      tool_name: toolName,
    };
  }

  return {
    type: "ok",
    success: true,
    data: parsed,
    tool_call_id: toolCallId,
    tool_name: toolName,
  };
}

export function normalizeToolResult(
  value: unknown,
  options: NormalizeToolResultOptions = {}
): Record<string, unknown> {
  const parsed = parseMaybeJson(value);

  if (isRecord(parsed) && "content" in parsed) {
    return normalizeParsedToolResult(parseMaybeJson(parsed.content), {
      status: parsed.status ?? options.status,
      toolCallId: parsed.tool_call_id ?? options.toolCallId,
      toolName: parsed.name ?? options.toolName,
      success: options.success,
    });
  }

  return normalizeParsedToolResult(parsed, options);
}
