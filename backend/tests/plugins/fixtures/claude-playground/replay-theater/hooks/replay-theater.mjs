// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0
//
// Replay Theater: records the file edits Claude makes in a turn, then lets you
// step through them in a pane, one diff at a time.
//
// Claude Code 2.1.280 function hooks. Load with --plugin-dir.

const PANE_ID = "replay-theater";
const MAX_DIFF_LINES = 12;
const MAX_LCS_LINES = 400;
const EDIT_TOOLS = new Set(["Edit", "Write", "MultiEdit"]);

// Module state. `pending` fills during a turn; `replay` is the last finished
// turn's steps, the ones the pane shows.
const state = { pending: [], replay: [], index: 0, isOpen: false, inBand: false, turns: 0 };

function relPath(cwd, path) {
  if (!path) return "(unknown file)";
  if (cwd && path.startsWith(cwd + "/")) return path.slice(cwd.length + 1);
  return path;
}

function splitLines(text) {
  if (text === undefined || text === null || text === "") return [];
  const lines = String(text).split("\n");
  if (lines.length > 1 && lines[lines.length - 1] === "") lines.pop();
  return lines;
}

// A line diff. Small inputs get an LCS diff, so unchanged lines show as
// context; large ones fall back to all-removed then all-added.
function diffLines(oldText, newText) {
  const a = splitLines(oldText);
  const b = splitLines(newText);
  if (a.length > MAX_LCS_LINES || b.length > MAX_LCS_LINES) {
    return [...a.map((t) => ({ op: "-", t })), ...b.map((t) => ({ op: "+", t }))];
  }
  const n = a.length, m = b.length;
  const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { out.push({ op: " ", t: a[i] }); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({ op: "-", t: a[i++] });
    else out.push({ op: "+", t: b[j++] });
  }
  while (i < n) out.push({ op: "-", t: a[i++] });
  while (j < m) out.push({ op: "+", t: b[j++] });
  return trimContext(out);
}

// Keep one line of context around each change, so a long file's Write shows
// the changed lines, not the whole file.
function trimContext(lines) {
  if (!lines.some((l) => l.op !== " ")) return lines.slice(0, MAX_DIFF_LINES);
  const keep = lines.map((l, k) =>
    l.op !== " " || lines[k - 1]?.op && lines[k - 1].op !== " " || lines[k + 1]?.op && lines[k + 1].op !== " ");
  const out = [];
  let skipped = false;
  lines.forEach((l, k) => {
    if (keep[k]) { if (skipped && out.length) out.push({ op: "~", t: "⋯" }); out.push(l); skipped = false; }
    else skipped = true;
  });
  return out;
}

function countChanges(diff) {
  let add = 0, del = 0;
  for (const l of diff) { if (l.op === "+") add++; else if (l.op === "-") del++; }
  return { add, del };
}

// Turns one tool call into one or more steps.
async function stepsFor($, e) {
  let cwd = "";
  try { cwd = await $.session.cwd(); } catch { /* keep the full path */ }
  const file = relPath(cwd, e.file_path);
  if (e.tool === "Edit") {
    return [{ tool: "Edit", file, diff: diffLines(e.old_string, e.new_string), note: e.replace_all ? "replace all" : "" }];
  }
  if (e.tool === "MultiEdit" && Array.isArray(e.edits)) {
    return e.edits.map((ed, k) => ({
      tool: "MultiEdit", file, diff: diffLines(ed.old_string, ed.new_string), note: `edit ${k + 1} of ${e.edits.length}`,
    }));
  }
  if (e.tool === "Write") {
    let before = "";
    let isNew = true;
    try {
      if (e.file_path && (await $.fs.exists(e.file_path))) {
        before = await $.fs.read(e.file_path);
        isNew = false;
      }
    } catch { /* unreadable: show it as a new file */ }
    return [{ tool: "Write", file, diff: diffLines(before, e.content), note: isNew ? "new file" : "rewrite" }];
  }
  return [];
}

function hintText() {
  const n = state.replay.length;
  return `▶ Replay: ${n} edit${n === 1 ? "" : "s"} (press r)`;
}

async function openReplay($) {
  if (!state.replay.length) return false;
  state.index = 0;
  state.isOpen = true;
  // The pane only takes the keyboard while nothing else holds it. Hide the
  // band first (it held the keys if its button was pressed), then open.
  $.ui.invalidate("ui.render");
  await $.clock.sleep(200);
  const rows = Math.min(MAX_DIFF_LINES + 8, 22);
  const placed = await $.ui.open({ id: PANE_ID, title: "Replay Theater", focus: true, closeOnEscape: true, rows, columns: 58 });
  // No room for a pane (a narrow terminal): draw the replay in the band.
  state.inBand = placed?.isPlaced === false;
  $.ui.invalidate("ui.render");
  return true;
}

// The replay view: one step at a time. Drawn in the Pane, or in the band
// above the prompt when the surface can't place a pane.
function replayView($, e, inBand) {
    const { Box, Text, Button } = $.ui.resolve(e);
    const maxDiff = inBand ? Math.max(3, Math.min(MAX_DIFF_LINES, (e.maxRows || 20) - 7)) : MAX_DIFF_LINES;
    const total = state.replay.length;
    if (!total) return Text({ dimColor: true, children: "No edits to replay." });
    const k = Math.max(0, Math.min(state.index, total - 1));
    const step = state.replay[k];
    const width = Math.max(40, (e.bodyColumns || 100) - 4);
    const { add, del } = countChanges(step.diff);
    const shown = step.diff.slice(0, maxDiff);

    const diffRows = shown.map((l, n) => {
      const color = l.op === "+" ? "green" : l.op === "-" ? "red" : undefined;
      const line = `${l.op === "~" ? " " : l.op} ${l.t}`.slice(0, width);
      return Text({ key: `d${n}`, color, dimColor: l.op === " " || l.op === "~", wrap: "truncate-end", children: line });
    });
    if (step.diff.length > maxDiff) diffRows.push(Text({ key: "more", dimColor: true, children: `  … ${step.diff.length - maxDiff} more lines` }));
    if (!shown.length) diffRows.push(Text({ key: "empty", dimColor: true, children: "  (no line changes)" }));

    // The step list: one cell per step, the current one highlighted.
    const strip = state.replay.map((s, n) =>
      Text({ key: `s${n}`, inverse: n === k, color: n === k ? "cyan" : undefined, dimColor: n !== k, children: ` ${n + 1} ` }));

    const go = (to) => { state.index = Math.max(0, Math.min(to, total - 1)); $.ui.invalidate("ui.render"); };
    const close = () => {
      state.isOpen = false;
      if (!state.inBand) $.ui.close({ id: PANE_ID });
      state.inBand = false;
      $.ui.invalidate("ui.render");
    };

    return Box({
      flexDirection: "column", borderStyle: "round", borderColor: "magenta", paddingX: 1,
      children: [
        Box({ flexDirection: "row", justifyContent: "space-between", children: [
          Text({ bold: true, color: "magenta", children: "▶ Replay Theater" }),
          Text({ bold: true, children: `step ${k + 1} of ${total}` }),
        ] }),
        Box({ flexDirection: "row", children: strip }),
        Text({ bold: true, color: "cyan", wrap: "truncate-start", children: step.file }),
        Box({ flexDirection: "row", gap: 2, children: [
          Text({ dimColor: true, children: `${step.tool}${step.note ? " · " + step.note : ""}` }),
          Text({ color: "green", children: `+${add}` }),
          Text({ color: "red", children: `-${del}` }),
        ] }),
        Box({ flexDirection: "column", marginTop: 1, children: diffRows }),
        Box({ flexDirection: "row", gap: 2, marginTop: 1, children: [
          Button({ key: "prev", label: "◀ Prev", hotkey: "p", onPress: () => go(k - 1) }),
          Button({ key: "next", label: "Next ▶", hotkey: "n", autoFocus: true, onPress: () => go(k + 1) }),
          Button({ key: "close", label: "Close", hotkey: "c", onPress: close }),
        ] }),
      ],
    });
}

export function register(on, options) {
  // Slash command: /replay opens the pane.
  on("session.start", async ($, e, next) => {
    const r = await next(e);
    await $.command.register({ name: "replay", description: "Replay Theater: step through the last turn's file edits" });
    return r;
  });

  on("command.run", { command: "replay" }, async ($, e) => {
    const opened = await openReplay($);
    return { text: opened ? `Replay Theater: ${state.replay.length} edits` : "Replay Theater: no edits in the last turn." };
  });

  // Record each edit, then let it run. Never blocks the call.
  on("tool.call", async ($, e, next) => {
    if (EDIT_TOOLS.has(e.tool)) {
      try {
        const steps = await stepsFor($, e);
        state.pending.push(...steps);
      } catch { /* recording must never stop the edit */ }
    }
    return next(e);
  });

  on("turn.start", ($, e, next) => {
    if (!e.agentId) state.pending = [];
    return next(e);
  });

  // At the end of a main-loop turn, the pending edits become the replay.
  on("turn.complete", async ($, e, next) => {
    const r = await next(e);
    if (e.agentId || !state.pending.length) return r;
    state.replay = state.pending;
    state.pending = [];
    state.index = 0;
    state.turns++;
    $.ui.invalidate("ui.render");
    return r;
  });

  // The band above the prompt: the hint and a button that opens the pane.
  on("ui.render", { component: "AbovePrompt" }, ($, e, next) => {
    if (state.isOpen && state.inBand) return replayView($, e, true);
    if (!state.replay.length || state.isOpen) return next(e);
    const { Box, Text, Button } = $.ui.resolve(e);
    return Box({
      flexDirection: "row", gap: 2, paddingX: 1,
      children: [
        Text({ color: "magenta", bold: true, children: hintText() }),
        Button({ key: "open-replay", label: "Replay", hotkey: "r", onPress: () => openReplay($) }),
      ],
    });
  });

  // The pane.
  on("ui.render", { component: "Pane" }, ($, e, next) => {
    if (e.requestId !== PANE_ID) return next(e);
    return replayView($, e, false);
  });

  // The person closed the pane (Escape): keep our flag in step.
  on("ui.close", ($, e, next) => {
    if (e.id === PANE_ID || e.requestId === PANE_ID) state.isOpen = false;
    $.ui.invalidate("ui.render");
    return next(e);
  });
}
