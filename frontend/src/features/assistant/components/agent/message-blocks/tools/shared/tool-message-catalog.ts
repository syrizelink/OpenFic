export const REGISTERED_TOOL_NAMES = [
  "dispatch_subagent",
  "notify_subagent",
  "recycle_subagent",
  "ask_user",
  "read_chapter",
  "write_chapter",
  "edit_chapter",
  "delete_chapter",
  "list_notes",
  "read_note",
  "write_note",
  "edit_note",
  "delete_note",
  "move_note",
  "create_note_category",
  "list_chapters",
  "list_volumes",
  "create_volume",
  "edit_volume",
  "delete_volume",
  "move_chapter_to_volume",
  "read_chapter_summaries",
  "read_range_summaries",
  "list_world_entries",
  "read_world_entry",
  "create_world_entry",
  "edit_world_entry",
  "delete_world_entry",
  "search_chapters",
  "update_index",
  "create_plan",
  "update_plan",
  "get_plan",
  "list_plan",
] as const;

export type RegisteredToolName = (typeof REGISTERED_TOOL_NAMES)[number];
export type ToolContentMode = "expandable" | "static" | "hidden";
export type ToolGroup =
  | "orchestration"
  | "interaction"
  | "chapter"
  | "note"
  | "volume"
  | "context"
  | "plan";

export interface ToolDescriptorMeta {
  toolName: RegisteredToolName;
  group: ToolGroup;
  tag: string;
  isExplore: boolean;
  contentMode: ToolContentMode;
}

const EXPLORE_TOOL_NAME_PREFIXES = ["get_", "list_", "read_", "search_"] as const;

export const TOOL_DESCRIPTOR_META = {
  dispatch_subagent: {
    toolName: "dispatch_subagent",
    group: "orchestration",
    tag: "dispatch",
    isExplore: false,
    contentMode: "expandable",
  },
  notify_subagent: {
    toolName: "notify_subagent",
    group: "orchestration",
    tag: "notify",
    isExplore: false,
    contentMode: "expandable",
  },
  recycle_subagent: {
    toolName: "recycle_subagent",
    group: "orchestration",
    tag: "recycle",
    isExplore: false,
    contentMode: "hidden",
  },
  ask_user: {
    toolName: "ask_user",
    group: "interaction",
    tag: "clarification",
    isExplore: false,
    contentMode: "expandable",
  },
  read_chapter: {
    toolName: "read_chapter",
    group: "chapter",
    tag: "read",
    isExplore: true,
    contentMode: "hidden",
  },
  write_chapter: {
    toolName: "write_chapter",
    group: "chapter",
    tag: "write",
    isExplore: false,
    contentMode: "expandable",
  },
  edit_chapter: {
    toolName: "edit_chapter",
    group: "chapter",
    tag: "edit",
    isExplore: false,
    contentMode: "expandable",
  },
  delete_chapter: {
    toolName: "delete_chapter",
    group: "chapter",
    tag: "delete",
    isExplore: false,
    contentMode: "hidden",
  },
  list_notes: {
    toolName: "list_notes",
    group: "note",
    tag: "list",
    isExplore: true,
    contentMode: "hidden",
  },
  read_note: {
    toolName: "read_note",
    group: "note",
    tag: "read",
    isExplore: true,
    contentMode: "hidden",
  },
  write_note: {
    toolName: "write_note",
    group: "note",
    tag: "write",
    isExplore: false,
    contentMode: "expandable",
  },
  edit_note: {
    toolName: "edit_note",
    group: "note",
    tag: "edit",
    isExplore: false,
    contentMode: "expandable",
  },
  delete_note: {
    toolName: "delete_note",
    group: "note",
    tag: "delete",
    isExplore: false,
    contentMode: "hidden",
  },
  move_note: {
    toolName: "move_note",
    group: "note",
    tag: "move",
    isExplore: false,
    contentMode: "static",
  },
  create_note_category: {
    toolName: "create_note_category",
    group: "note",
    tag: "write",
    isExplore: false,
    contentMode: "hidden",
  },
  list_chapters: {
    toolName: "list_chapters",
    group: "chapter",
    tag: "list",
    isExplore: true,
    contentMode: "hidden",
  },
  list_volumes: {
    toolName: "list_volumes",
    group: "volume",
    tag: "list",
    isExplore: true,
    contentMode: "hidden",
  },
  create_volume: {
    toolName: "create_volume",
    group: "volume",
    tag: "create",
    isExplore: false,
    contentMode: "hidden",
  },
  edit_volume: {
    toolName: "edit_volume",
    group: "volume",
    tag: "edit",
    isExplore: false,
    contentMode: "hidden",
  },
  delete_volume: {
    toolName: "delete_volume",
    group: "volume",
    tag: "delete",
    isExplore: false,
    contentMode: "hidden",
  },
  move_chapter_to_volume: {
    toolName: "move_chapter_to_volume",
    group: "volume",
    tag: "move",
    isExplore: false,
    contentMode: "hidden",
  },
  read_chapter_summaries: {
    toolName: "read_chapter_summaries",
    group: "context",
    tag: "chapter-summary",
    isExplore: true,
    contentMode: "hidden",
  },
  read_range_summaries: {
    toolName: "read_range_summaries",
    group: "context",
    tag: "range-summary",
    isExplore: true,
    contentMode: "hidden",
  },
  list_world_entries: {
    toolName: "list_world_entries",
    group: "context",
    tag: "world-entry-list",
    isExplore: true,
    contentMode: "hidden",
  },
  read_world_entry: {
    toolName: "read_world_entry",
    group: "context",
    tag: "world-entry-read",
    isExplore: true,
    contentMode: "hidden",
  },
  create_world_entry: {
    toolName: "create_world_entry",
    group: "context",
    tag: "world-entry-create",
    isExplore: false,
    contentMode: "expandable",
  },
  edit_world_entry: {
    toolName: "edit_world_entry",
    group: "context",
    tag: "world-entry-edit",
    isExplore: false,
    contentMode: "expandable",
  },
  delete_world_entry: {
    toolName: "delete_world_entry",
    group: "context",
    tag: "world-entry-delete",
    isExplore: false,
    contentMode: "hidden",
  },
  search_chapters: {
    toolName: "search_chapters",
    group: "chapter",
    tag: "search",
    isExplore: true,
    contentMode: "hidden",
  },
  update_index: {
    toolName: "update_index",
    group: "chapter",
    tag: "update-index",
    isExplore: false,
    contentMode: "hidden",
  },
  create_plan: {
    toolName: "create_plan",
    group: "plan",
    tag: "create",
    isExplore: false,
    contentMode: "expandable",
  },
  update_plan: {
    toolName: "update_plan",
    group: "plan",
    tag: "update",
    isExplore: false,
    contentMode: "expandable",
  },
  get_plan: {
    toolName: "get_plan",
    group: "plan",
    tag: "read",
    isExplore: false,
    contentMode: "expandable",
  },
  list_plan: {
    toolName: "list_plan",
    group: "plan",
    tag: "list",
    isExplore: false,
    contentMode: "expandable",
  },
} satisfies Record<RegisteredToolName, ToolDescriptorMeta>;

export function isExploreToolName(toolName?: string): boolean {
  if (!toolName) return false;
  if (EXPLORE_TOOL_NAME_PREFIXES.some((prefix) => toolName.startsWith(prefix))) return true;
  return Boolean(TOOL_DESCRIPTOR_META[toolName as RegisteredToolName]?.isExplore);
}

export function getToolDescriptorMeta(toolName?: string): ToolDescriptorMeta | null {
  if (!toolName) return null;
  const descriptor = TOOL_DESCRIPTOR_META[toolName as RegisteredToolName] ?? null;
  if (!descriptor) return null;
  const isExplore = isExploreToolName(toolName);
  return descriptor.isExplore === isExplore ? descriptor : { ...descriptor, isExplore };
}

export function getExploreToolNames(): RegisteredToolName[] {
  return REGISTERED_TOOL_NAMES.filter((toolName) => isExploreToolName(toolName));
}
