import type { SkillCreate } from "@/lib/skill.types";

interface ParsedFrontmatter {
  name?: string;
  description?: string;
}

function parseFrontmatter(content: string): ParsedFrontmatter | null {
  const trimmed = content.trim();
  if (!trimmed.startsWith("---")) return null;

  const endIndex = trimmed.indexOf("\n---", 3);
  if (endIndex === -1) return null;

  const block = trimmed.slice(3, endIndex).trimEnd();
  const lines = block.split("\n");
  const result: ParsedFrontmatter = {};

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const colonIndex = line.indexOf(":");
    if (colonIndex === -1) {
      i++;
      continue;
    }

    const key = line.slice(0, colonIndex).trim();
    const afterColon = line.slice(colonIndex + 1);

    if (key !== "name" && key !== "description") {
      i++;
      continue;
    }

    const trimmedAfter = afterColon.trim();

    if (trimmedAfter === "|" || trimmedAfter === ">") {
      const isFolded = trimmedAfter === ">";
      i++;
      const indentMatch = lines[i]?.match(/^(\s+)/);
      const baseIndent = indentMatch ? indentMatch[1].length : 0;
      const collected: string[] = [];

      while (i < lines.length) {
        const currentLine = lines[i];
        if (currentLine.trim() === "") {
          collected.push("");
          i++;
          continue;
        }
        const currentIndent = currentLine.match(/^(\s+)/)?.[1].length ?? 0;
        if (currentIndent < baseIndent) break;
        collected.push(currentLine.slice(baseIndent));
        i++;
      }

      const value = isFolded
        ? collected
            .reduce<string[]>((acc, cur) => {
              if (cur === "") {
                acc.push("");
              } else if (acc.length > 0 && acc[acc.length - 1] !== "") {
                acc[acc.length - 1] += " " + cur;
              } else {
                acc.push(cur);
              }
              return acc;
            }, [])
            .join("\n")
            .trim()
        : collected.join("\n").trimEnd();

      if (key === "name") result.name = value;
      else result.description = value;
    } else if (trimmedAfter) {
      if (key === "name") result.name = trimmedAfter;
      else result.description = trimmedAfter;
      i++;
    } else {
      i++;
    }
  }

  if (!result.name && !result.description) return null;
  return result;
}

const SKILL_ID_RE = /^[a-z]+(?:-[a-z]+)*$/;

export function parseSkillMarkdown(markdown: string): SkillCreate {
  const frontmatter = parseFrontmatter(markdown);

  if (frontmatter?.name || frontmatter?.description) {
    const endIndex = markdown.indexOf("\n---", 3);
    const body = markdown.slice(endIndex + 4).trim();

    const name = frontmatter.name ?? "";
    const skillId = SKILL_ID_RE.test(name) ? name : "";

    return {
      name,
      summary: frontmatter.description ?? "",
      skillId,
      content: body,
      isEnabled: false,
    };
  }

  return {
    name: "",
    summary: "",
    skillId: "",
    content: markdown.trim(),
    isEnabled: false,
  };
}
