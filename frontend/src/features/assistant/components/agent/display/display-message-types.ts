import type {
  AgentMessage,
  ClarificationQuestion,
  ToolApprovalData,
} from "@/lib/agent.types";

type DisplayMessageOf<TType extends string> = Omit<AgentMessage, "type"> & {
  type: TType;
};

export type UserDisplayMessage = DisplayMessageOf<"user_request"> & {
  role?: "user";
};

export type AgentOutputDisplayMessage = DisplayMessageOf<"agent_output"> & {
  role?: "assistant";
};

export type ReasoningDisplayMessage = DisplayMessageOf<"reasoning">;

export type ToolDisplayMessage = DisplayMessageOf<"tool"> & {
  toolName: string;
};

export type RetryDisplayMessage = DisplayMessageOf<"retry">;

export type CompactionDisplayMessage = DisplayMessageOf<"compaction">;

export type CompletedDisplayMessage = DisplayMessageOf<"completed">;

export type ErrorDisplayMessage = DisplayMessageOf<"error">;

export type NodeStartDisplayMessage = DisplayMessageOf<"node_start">;

export type NodeEndDisplayMessage = DisplayMessageOf<"node_end">;

export type BlockDisplayMessage =
  | UserDisplayMessage
  | AgentOutputDisplayMessage
  | ReasoningDisplayMessage
  | ToolDisplayMessage
  | RetryDisplayMessage
  | CompactionDisplayMessage
  | CompletedDisplayMessage
  | ErrorDisplayMessage
  | NodeStartDisplayMessage
  | NodeEndDisplayMessage;

export type RenderableDisplayMessage = Exclude<BlockDisplayMessage, NodeEndDisplayMessage>;

export type AgentBlockDisplayMessage = Exclude<
  BlockDisplayMessage,
  UserDisplayMessage | NodeStartDisplayMessage | NodeEndDisplayMessage
>;

export type ApprovalPanelItem = DisplayMessageOf<"approval"> & {
  toolApproval: ToolApprovalData;
};

export type QuestionPanelItem = DisplayMessageOf<"question"> & {
  questions: ClarificationQuestion[];
};

export type SpecialPanelItem = ApprovalPanelItem | QuestionPanelItem;

export function isRenderableDisplayMessage(
  message: BlockDisplayMessage
): message is RenderableDisplayMessage {
  return message.type !== "node_end";
}

export function isQuestionPanelItem(item: SpecialPanelItem): item is QuestionPanelItem {
  return item.type === "question";
}
