import type {
  ActiveSubagentState,
  AgentConversationDescriptor,
  ParentConversationDescriptor,
  SubagentConversationDescriptor,
} from "@/lib/agent.types";

export interface ParentConversationEntry extends ParentConversationDescriptor {
  taskId?: string | null;
  taskTitle?: string | null;
}

export interface SubagentConversationEntry extends SubagentConversationDescriptor {
  subagent: ActiveSubagentState;
}

export type AssistantConversationEntry = ParentConversationEntry | SubagentConversationEntry;

export interface AssistantConversationStackState {
  entries: AssistantConversationEntry[];
}

export function createConversationStackState(sessionId: string): AssistantConversationStackState {
  return {
    entries: [{ kind: "parent", sessionId }],
  };
}

export function getCurrentConversationDescriptor(
  state: AssistantConversationStackState,
): AgentConversationDescriptor | null {
  const current = state.entries.at(-1);
  if (!current) return null;
  if (current.kind === "parent") {
    return { kind: "parent", sessionId: current.sessionId };
  }
  return {
    kind: "subagent",
    childRunId: current.childRunId,
    childThreadId: current.childThreadId,
    parentSessionId: current.parentSessionId,
  };
}

export function getCurrentSubagentSnapshot(
  state: AssistantConversationStackState,
): ActiveSubagentState | null {
  const current = state.entries.at(-1);
  return current?.kind === "subagent" ? current.subagent : null;
}

export function syncParentConversationState(
  state: AssistantConversationStackState,
  sessionId: string,
): AssistantConversationStackState {
  const parentEntry = state.entries[0];
  const parentSessionId = parentEntry?.kind === "parent" ? parentEntry.sessionId : undefined;
  if (parentSessionId === sessionId && state.entries.length > 0) {
    return state;
  }
  return createConversationStackState(sessionId);
}

export function openSubagentConversation(
  state: AssistantConversationStackState,
  parentSessionId: string,
  subagent: ActiveSubagentState,
): AssistantConversationStackState {
  const synced = syncParentConversationState(state, parentSessionId);
  return {
    entries: [
      synced.entries[0],
      {
        kind: "subagent",
        childRunId: subagent.childRunId,
        childThreadId: subagent.childThreadId,
        parentSessionId,
        subagent,
      },
    ],
  };
}

export function returnToPrimaryConversation(
  state: AssistantConversationStackState,
): AssistantConversationStackState {
  const parentEntry = state.entries[0];
  if (!parentEntry) return createConversationStackState("");
  return {
    entries: [parentEntry],
  };
}
