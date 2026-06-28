const UTC_TIMEZONE_PATTERN = /(?:Z|[+-]\d{2}:?\d{2})$/i;

export function normalizeUtcDateString(value: string | null | undefined): string {
  if (typeof value !== "string" || !value) return "";
  if (UTC_TIMEZONE_PATTERN.test(value)) return value;
  return `${value}Z`;
}

export function parseUtcTimestamp(value: string | null | undefined, fallback = Date.now()): number {
  const normalized = normalizeUtcDateString(value);
  if (!normalized) return fallback;
  const timestamp = new Date(normalized).getTime();
  return Number.isFinite(timestamp) ? timestamp : fallback;
}
