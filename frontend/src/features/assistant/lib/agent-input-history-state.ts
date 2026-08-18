export const AGENT_INPUT_HISTORY_LIMIT = 50;

export type AgentInputHistoryDirection = "older" | "newer";

export function normalizeAgentInputDraft(value: string): string {
  return value.trim() ? value : "";
}

export interface AgentInputHistoryState {
  entries: string[];
  index: number | null;
  draft: string;
}

export interface AgentInputHistoryNavigationResult {
  state: AgentInputHistoryState;
  value: string;
  handled: boolean;
}

export function appendAgentInputHistory(entries: string[], value: string): string[] {
  if (!value.trim() || entries.at(-1) === value) return entries;
  return [...entries, value].slice(-AGENT_INPUT_HISTORY_LIMIT);
}

export function createAgentInputHistoryState(entries: string[]): AgentInputHistoryState {
  return {
    entries: entries.slice(-AGENT_INPUT_HISTORY_LIMIT),
    index: null,
    draft: "",
  };
}

export function applyAgentInputChange(
  state: AgentInputHistoryState,
  value: string,
): AgentInputHistoryState {
  return {
    ...state,
    index: null,
    draft: value,
  };
}

export function navigateAgentInputHistory(
  state: AgentInputHistoryState,
  direction: AgentInputHistoryDirection,
  currentValue: string,
): AgentInputHistoryNavigationResult {
  if (direction === "older") {
    const nextIndex = state.index === null ? state.entries.length - 1 : state.index - 1;
    if (nextIndex < 0) {
      return { state, value: currentValue, handled: false };
    }

    return {
      state: {
        ...state,
        index: nextIndex,
        draft: state.index === null ? currentValue : state.draft,
      },
      value: state.entries[nextIndex],
      handled: true,
    };
  }

  if (state.index === null) {
    return { state, value: currentValue, handled: false };
  }

  const nextIndex = state.index + 1;
  if (nextIndex < state.entries.length) {
    return {
      state: { ...state, index: nextIndex },
      value: state.entries[nextIndex],
      handled: true,
    };
  }

  return {
    state: { ...state, index: null },
    value: state.draft,
    handled: true,
  };
}
