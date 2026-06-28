export interface AssistantMentionCandidate {
  kind: "volume" | "chapter" | "note" | "note_category";
  id: string;
  title: string;
  label: string;
  description?: string;
}

export interface AssistantMentionSearchResponse {
  items: AssistantMentionCandidate[];
}
