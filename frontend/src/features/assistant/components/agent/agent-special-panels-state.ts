import type { AgentMessage, ToolApprovalData } from "../../../../lib/agent.types";

import {
  getClarificationPromptData,
  type ClarificationPromptData,
} from "./message-blocks/messages/special/clarification-flow-state";

export type AgentSpecialPanelVariant = "card" | "flat";

export interface AgentApprovalSpecialPanel {
  id: string;
  kind: "approval";
  approval: ToolApprovalData;
  summary: string;
}

export interface AgentQuestionSpecialPanel {
  id: string;
  kind: "question";
  prompt: ClarificationPromptData;
  summary: string;
}

export type AgentSpecialPanel = AgentApprovalSpecialPanel | AgentQuestionSpecialPanel;

const ACTIVE_SPECIAL_PANEL_STATUSES = new Set<NonNullable<AgentMessage["status"]>>(["pending", "running"]);

function getStringArg(args: Record<string, unknown>, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = args[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return undefined;
}

function getApprovalSummary(toolName: string, toolArgs: Record<string, unknown>): string {
  const title = getStringArg(toolArgs, "title", "chapter_title", "name");
  const chapterLabel = title ?? getStringArg(toolArgs, "chapter_id") ?? "章节";

  switch (toolName) {
    case "write_chapter":
      return `写入 ${chapterLabel}`;
    case "edit_chapter":
      return `编辑 ${chapterLabel}`;
    case "delete_chapter":
      return `删除 ${chapterLabel}`;
    case "move_chapter":
      return `移动 ${chapterLabel}`;
    case "rename_chapter":
      return `重命名 ${chapterLabel}`;
    case "set_chapter_content":
      return `更新 ${chapterLabel}`;
    case "apply_chapter_operations":
      return "批量修改章节";
    default:
      return toolName ? `执行 ${toolName}` : "执行工具调用";
  }
}

function isVisibleActiveSpecialPanelMessage(message: AgentMessage): boolean {
  if (message.display === "hidden") return false;
  return !message.status || ACTIVE_SPECIAL_PANEL_STATUSES.has(message.status);
}

function getQuestionSummary(prompt: ClarificationPromptData): string {
  return `${prompt.questions.length} 个待回答问题`;
}

export function getAgentSpecialPanels(messages: AgentMessage[]): AgentSpecialPanel[] {
  return messages.reduce<AgentSpecialPanel[]>((panels, message) => {
    if (!isVisibleActiveSpecialPanelMessage(message)) return panels;

    if (message.type === "question") {
      const prompt = getClarificationPromptData(message);
      if (prompt.questions.length === 0) return panels;

      panels.push({
        id: message.id,
        kind: "question",
        prompt,
        summary: getQuestionSummary(prompt),
      });
      return panels;
    }

    if ((message.type === "approval" || message.type === "tool_approval") && message.toolApproval) {
      panels.push({
        id: message.id,
        kind: "approval",
        approval: message.toolApproval,
        summary: getApprovalSummary(message.toolApproval.tool_name, message.toolApproval.tool_args),
      });
    }

    return panels;
  }, []);
}

export function getAgentSpecialPanelVariant(embedded: boolean): AgentSpecialPanelVariant {
  return embedded ? "flat" : "card";
}
