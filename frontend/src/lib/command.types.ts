import type { AssistantMentionCandidate } from "./mention.types";

export interface AssistantCommandCandidate {
  kind: "skill";
  id: string;
  name: string;
  description: string;
}

export interface AgentComposerItems {
  skills: AssistantCommandCandidate[];
  chapters: AssistantMentionCandidate[];
  notes: AssistantMentionCandidate[];
  worldInfoEntries: AssistantMentionCandidate[];
}
