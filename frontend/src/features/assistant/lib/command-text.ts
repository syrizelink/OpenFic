export type { AssistantCommandCandidate } from "@/lib/command.types";

export type AssistantCommandKind = "skill";

export interface AssistantCommandToken {
  markup: "command";
  raw: string;
  kind: AssistantCommandKind;
  attrs: Record<string, string>;
  body: string;
}

const ATTR_RE = /([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"/g;

export function buildSkillCommandTag(id: string, name: string): string {
  return (
    `<of-skill id="${escapeCommandAttribute(id)}" ` + `name="${escapeCommandAttribute(name)}" />`
  );
}

export function getCommandDisplayLabel(token: AssistantCommandToken): string {
  return token.attrs.name?.trim() || token.kind;
}

export function parseCommandAttributes(rawAttrs: string): Record<string, string> {
  return Array.from(rawAttrs.matchAll(ATTR_RE)).reduce<Record<string, string>>((result, match) => {
    const [, key, value] = match;
    if (!key) return result;
    result[key] = decodeCommandEntities(value ?? "");
    return result;
  }, {});
}

export function findActiveCommandQuery(textBeforeCursor: string): {
  query: string;
  replaceLength: number;
} | null {
  const match = textBeforeCursor.match(/(?:^|\s)\/([^\s/]*)$/);
  if (!match) return null;
  const query = match[1] ?? "";
  return {
    query,
    replaceLength: query.length + 1,
  };
}

function escapeCommandAttribute(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function decodeCommandEntities(text: string): string {
  return text
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}
