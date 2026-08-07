export interface StreamingBlockState {
  readonly blocks: readonly string[];
  readonly active: string;
  readonly fenceMarker: string | null;
  readonly mathOpen: boolean;
}

export function createStreamingBlockState(): StreamingBlockState {
  return { blocks: [], active: "", fenceMarker: null, mathOpen: false };
}

const FENCE_OPEN_RE = /^\s*(`{3,}|~{3,})(.*)$/;
const FENCE_CLOSE_RE = /^\s*(`{3,}|~{3,})\s*$/;
const MATH_BOUNDARY_RE = /^\s*\$\$\s*$/;
const HEADING_RE = /^\s{0,3}#{1,6}\s/;
const BLANK_LINE_RE = /^\s*$/;

export function appendStreamingBlockContent(
  state: StreamingBlockState,
  delta: string,
): StreamingBlockState {
  if (delta.length === 0) return state;

  const pending = state.active + delta;
  const endsWithNewline = pending.endsWith("\n");
  const segments = pending.split("\n");
  if (endsWithNewline && segments[segments.length - 1] === "") {
    segments.pop();
  }
  const incomplete = endsWithNewline ? "" : (segments.pop() ?? "");

  let blocks = state.blocks;
  let current = "";
  let fenceMarker = state.fenceMarker;
  let mathOpen = state.mathOpen;

  const finalize = () => {
    if (current.length > 0) {
      blocks = [...blocks, `${current}\n`];
      current = "";
    }
  };

  for (const rawLine of segments) {
    const line = rawLine.replace(/\r$/, "");

    if (fenceMarker !== null) {
      current += `${line}\n`;
      const close = FENCE_CLOSE_RE.exec(line);
      if (close && close[1] === fenceMarker) {
        fenceMarker = null;
        finalize();
      }
      continue;
    }

    if (mathOpen) {
      current += `${line}\n`;
      if (MATH_BOUNDARY_RE.test(line)) {
        mathOpen = false;
        finalize();
      }
      continue;
    }

    if (BLANK_LINE_RE.test(line)) {
      finalize();
      continue;
    }

    const fenceOpen = FENCE_OPEN_RE.exec(line);
    if (fenceOpen && fenceOpen[1].length >= 3) {
      finalize();
      fenceMarker = fenceOpen[1];
      current = `${line}\n`;
      continue;
    }

    if (MATH_BOUNDARY_RE.test(line)) {
      finalize();
      mathOpen = true;
      current = `${line}\n`;
      continue;
    }

    if (HEADING_RE.test(line)) {
      finalize();
      current = `${line}\n`;
      continue;
    }

    current += `${line}\n`;
  }

  return { blocks, active: `${current}${incomplete}`, fenceMarker, mathOpen };
}
