export const PARAGRAPH_INDENT = "\u3000\u3000";

export interface TextReplacement {
  from: number;
  to: number;
  text: string;
}

export function getParagraphIndentAction(paragraphStart: number): TextReplacement {
  return {
    from: paragraphStart,
    to: paragraphStart,
    text: PARAGRAPH_INDENT,
  };
}

export function isParagraphIndented(paragraphText: string): boolean {
  return paragraphText.startsWith(PARAGRAPH_INDENT);
}

export interface QuoteInsertion {
  text: string;
  cursorOffset: number;
}

export function getSmartQuoteInsertion(textBeforeCursor: string): QuoteInsertion {
  const openingQuoteCount = Array.from(textBeforeCursor).filter((char) => char === "“").length;
  const closingQuoteCount = Array.from(textBeforeCursor).filter((char) => char === "”").length;

  return openingQuoteCount > closingQuoteCount
    ? { text: "”", cursorOffset: 1 }
    : { text: "“”", cursorOffset: 1 };
}

export function getParagraphOutdentAction(
  paragraphStart: number,
  paragraphText: string,
): TextReplacement | null {
  if (!isParagraphIndented(paragraphText)) return null;

  return {
    from: paragraphStart,
    to: paragraphStart + PARAGRAPH_INDENT.length,
    text: "",
  };
}
