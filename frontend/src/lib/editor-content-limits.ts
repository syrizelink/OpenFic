export const MAX_EDITOR_CONTENT_LINES = 2_000;
export const MAX_EDITOR_CONTENT_CHARACTERS = 100_000;

const LINE_SEPARATORS = new Set([
  "\n",
  "\r",
  "\u000B",
  "\u000C",
  "\u001C",
  "\u001D",
  "\u001E",
  "\u0085",
  "\u2028",
  "\u2029",
]);

export interface EditorContentLimit {
  lineCount: number;
  characterCount: number;
  isWithinLimit: boolean;
}

function countEditorContentLines(content: string): number {
  if (content === "") return 0;

  let separatorCount = 0;
  let endsWithSeparator = false;
  for (let index = 0; index < content.length; index += 1) {
    const character = content[index] ?? "";
    if (!LINE_SEPARATORS.has(character)) {
      endsWithSeparator = false;
      continue;
    }

    separatorCount += 1;
    if (character === "\r" && content[index + 1] === "\n") index += 1;
    endsWithSeparator = index === content.length - 1;
  }

  return endsWithSeparator ? separatorCount : separatorCount + 1;
}

export function getEditorContentLimit(content: string): EditorContentLimit {
  const lineCount = countEditorContentLines(content);
  const characterCount = Array.from(content).length;

  return {
    lineCount,
    characterCount,
    isWithinLimit:
      lineCount <= MAX_EDITOR_CONTENT_LINES && characterCount <= MAX_EDITOR_CONTENT_CHARACTERS,
  };
}
