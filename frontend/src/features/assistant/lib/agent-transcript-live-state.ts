import type { AgentEvent } from "@/lib/agent.types";

import {
  applyAgentTranscriptEvent,
  type AgentTranscriptEventOptions,
  type AgentTranscriptEventResult,
  type AgentTranscriptState,
} from "./agent-transcript-state";

export type AgentTranscriptLiveState = AgentTranscriptState;

export function createAgentTranscriptLiveState(
  initial: Partial<AgentTranscriptState> = {},
): AgentTranscriptLiveState {
  return {
    messages: initial.messages ?? [],
    status: initial.status ?? "idle",
    isRunning: initial.isRunning ?? false,
    currentStage: initial.currentStage ?? "",
  };
}

export function syncAgentTranscriptLiveState(
  liveState: AgentTranscriptLiveState,
  nextState: AgentTranscriptState,
): AgentTranscriptState {
  liveState.messages = nextState.messages;
  liveState.status = nextState.status;
  liveState.isRunning = nextState.isRunning;
  liveState.currentStage = nextState.currentStage;
  return nextState;
}

export function applyAgentTranscriptEventToLiveState(
  liveState: AgentTranscriptLiveState,
  event: AgentEvent,
  options: AgentTranscriptEventOptions = {},
): AgentTranscriptEventResult {
  const result = applyAgentTranscriptEvent(liveState, event, options);
  syncAgentTranscriptLiveState(liveState, result.state);
  return result;
}
