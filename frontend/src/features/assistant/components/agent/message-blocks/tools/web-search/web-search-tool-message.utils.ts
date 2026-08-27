export interface WebSearchResultPayload {
  title: string;
  url: string;
  snippet: string;
}

export interface WebSearchData {
  query?: string;
  provider?: string;
  answer?: string;
  results: WebSearchResultPayload[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function asTrimmedString(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return trimmed || undefined;
}

export function isSafeWebSearchUrl(value: string): boolean {
  try {
    const protocol = new URL(value).protocol;
    return protocol === "http:" || protocol === "https:";
  } catch {
    return false;
  }
}

export function getWebSearchFaviconUrl(value: string): string | undefined {
  if (!isSafeWebSearchUrl(value)) return undefined;
  return `${new URL(value).origin}/favicon.ico`;
}

export function normalizeWebSearchData(value: unknown): WebSearchData {
  const data = isRecord(value) ? value : {};
  const results = Array.isArray(data.results)
    ? data.results
        .filter(isRecord)
        .map((result) => ({
          title: asTrimmedString(result.title) ?? "",
          url: asTrimmedString(result.url) ?? "",
          snippet: asTrimmedString(result.snippet) ?? "",
        }))
        .filter((result) => result.title || result.url || result.snippet)
    : [];

  return {
    query: asTrimmedString(data.query),
    provider: asTrimmedString(data.provider),
    answer: asTrimmedString(data.answer),
    results,
  };
}
