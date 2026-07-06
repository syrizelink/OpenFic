import i18n from "@/i18n";

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

const ACTIVE_SPECIAL_PANEL_STATUSES = new Set<NonNullable<AgentMessage["status"]>>([
  "pending",
  "running",
]);

function getStringArg(args: Record<string, unknown>, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = args[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return undefined;
}

function getApprovalSummary(toolName: string, toolArgs: Record<string, unknown>): string {
  const title = getStringArg(toolArgs, "title", "chapter_title", "name");
  const chapterLabel =
    title ?? getStringArg(toolArgs, "chapter_id") ?? i18n.t("assistant.tools.chapter");

  switch (toolName) {
    case "write_chapter":
      return `${i18n.t("assistant.tools.writeChapter")} ${chapterLabel}`;
    case "edit_chapter":
      return `${i18n.t("assistant.tools.editChapter")} ${chapterLabel}`;
    case "delete_chapter":
      return `${i18n.t("assistant.tools.deleteChapter")} ${chapterLabel}`;
    case "move_chapter":
      return `${i18n.t("assistant.tools.moveChapterToVolume")} ${chapterLabel}`;
    case "rename_chapter":
      return `${i18n.t("chapterMenu.rename")} ${chapterLabel}`;
    case "set_chapter_content":
      return `${i18n.t("assistant.tools.content")} ${chapterLabel}`;
    case "apply_chapter_operations":
      return i18n.t("assistant.batchEditChapters");
    default:
      return toolName
        ? i18n.t("assistant.executeTool", { toolName })
        : i18n.t("assistant.executeToolCall");
  }
}

function isVisibleActiveSpecialPanelMessage(message: AgentMessage): boolean {
  if (message.display === "hidden") return false;
  return !message.status || ACTIVE_SPECIAL_PANEL_STATUSES.has(message.status);
}

function getQuestionSummary(prompt: ClarificationPromptData): string {
  return i18n.t("assistant.tools.questionCount", { count: prompt.questions.length });
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
