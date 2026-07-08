export interface AssistantMentionCandidate {
  kind: "volume" | "chapter" | "note" | "note_category" | "world_info_entry" | "character";
  id: string;
  title: string;
  label: string;
  description?: string;
}

export interface AssistantMentionSearchResponse {
  items: AssistantMentionCandidate[];
}
