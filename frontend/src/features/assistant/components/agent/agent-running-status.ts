import type { AgentMessage } from "@/lib/agent.types";

export const AGENT_RUNNING_STATUS = {
  considering: "considering",
  thinking: "thinking",
  writingReply: "writingReply",
  orchestration: "orchestration",
  interaction: "interaction",
  plan: "plan",
  chapterRead: "chapterRead",
  summaryRead: "summaryRead",
  characterRead: "characterRead",
  characterWrite: "characterWrite",
  worldRead: "worldRead",
  worldWrite: "worldWrite",
  noteRead: "noteRead",
  noteWrite: "noteWrite",
  chapterWrite: "chapterWrite",
  callingSkill: "callingSkill",
} as const;

export type AgentRunningStatus = (typeof AGENT_RUNNING_STATUS)[keyof typeof AGENT_RUNNING_STATUS];

const TOOL_RUNNING_STATUS: Record<string, AgentRunningStatus> = {
  dispatch_subagent: AGENT_RUNNING_STATUS.orchestration,
  notify_subagent: AGENT_RUNNING_STATUS.orchestration,
  recycle_subagent: AGENT_RUNNING_STATUS.orchestration,
  ask_user: AGENT_RUNNING_STATUS.interaction,
  write_plan: AGENT_RUNNING_STATUS.plan,
  list_volumes: AGENT_RUNNING_STATUS.chapterRead,
  list_chapters: AGENT_RUNNING_STATUS.chapterRead,
  read_chapter: AGENT_RUNNING_STATUS.chapterRead,
  search_chapters: AGENT_RUNNING_STATUS.chapterRead,
  update_index: AGENT_RUNNING_STATUS.chapterRead,
  read_chapter_summaries: AGENT_RUNNING_STATUS.summaryRead,
  read_range_summaries: AGENT_RUNNING_STATUS.summaryRead,
  list_characters: AGENT_RUNNING_STATUS.characterRead,
  read_character: AGENT_RUNNING_STATUS.characterRead,
  create_character: AGENT_RUNNING_STATUS.characterWrite,
  edit_character: AGENT_RUNNING_STATUS.characterWrite,
  delete_character: AGENT_RUNNING_STATUS.characterWrite,
  list_world_entries: AGENT_RUNNING_STATUS.worldRead,
  read_world_entry: AGENT_RUNNING_STATUS.worldRead,
  create_world_entry: AGENT_RUNNING_STATUS.worldWrite,
  edit_world_entry: AGENT_RUNNING_STATUS.worldWrite,
  delete_world_entry: AGENT_RUNNING_STATUS.worldWrite,
  list_notes: AGENT_RUNNING_STATUS.noteRead,
  read_note: AGENT_RUNNING_STATUS.noteRead,
  write_note: AGENT_RUNNING_STATUS.noteWrite,
  edit_note: AGENT_RUNNING_STATUS.noteWrite,
  delete_note: AGENT_RUNNING_STATUS.noteWrite,
  move_note: AGENT_RUNNING_STATUS.noteWrite,
  create_note_category: AGENT_RUNNING_STATUS.noteWrite,
  edit_note_category: AGENT_RUNNING_STATUS.noteWrite,
  delete_note_category: AGENT_RUNNING_STATUS.noteWrite,
  write_chapter: AGENT_RUNNING_STATUS.chapterWrite,
  edit_chapter: AGENT_RUNNING_STATUS.chapterWrite,
  delete_chapter: AGENT_RUNNING_STATUS.chapterWrite,
  create_volume: AGENT_RUNNING_STATUS.chapterWrite,
  edit_volume: AGENT_RUNNING_STATUS.chapterWrite,
  delete_volume: AGENT_RUNNING_STATUS.chapterWrite,
  move_chapter_to_volume: AGENT_RUNNING_STATUS.chapterWrite,
  activate_skill: AGENT_RUNNING_STATUS.callingSkill,
  reference_skill: AGENT_RUNNING_STATUS.callingSkill,
};

function isRunningMessage(message: AgentMessage): boolean {
  return message.status === "running" || message.isStreaming === true;
}

function getFirstToolNameInBatch(
  messages: AgentMessage[],
  activeIndex: number,
): string | undefined {
  let firstToolIndex = activeIndex;
  while (messages[firstToolIndex - 1]?.type === "tool") firstToolIndex -= 1;
  return messages[firstToolIndex]?.toolName;
}

export function getAgentRunningStatus(messages: AgentMessage[]): AgentRunningStatus | null {
  const activeIndex = messages.findLastIndex(isRunningMessage);
  if (activeIndex < 0) return AGENT_RUNNING_STATUS.considering;

  const activeMessage = messages[activeIndex];
  if (activeMessage.type === "reasoning") return AGENT_RUNNING_STATUS.thinking;
  if (
    activeMessage.type === "agent_output" ||
    (activeMessage.type === "text" && activeMessage.role === "assistant")
  ) {
    return AGENT_RUNNING_STATUS.writingReply;
  }
  if (activeMessage.type === "node_start") return AGENT_RUNNING_STATUS.considering;
  if (activeMessage.type !== "tool") return null;

  const toolName = getFirstToolNameInBatch(messages, activeIndex);
  return TOOL_RUNNING_STATUS[toolName ?? ""] ?? AGENT_RUNNING_STATUS.considering;
}
