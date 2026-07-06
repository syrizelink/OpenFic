import i18n from "@/i18n";

import {
  getToolDescriptorMeta,
  isExploreToolName,
} from "../message-blocks/tools/shared/tool-message-catalog";
import type { AgentBlockDisplayMessage, ToolDisplayMessage } from "./display-message-types";

export interface ExplorationSummary {
  chapterCount: number;
  listCount: number;
  contextCount: number;
  infoCount: number;
}

export type AgentDisplayItem =
  | {
      id: string;
      type: "message";
      message: AgentBlockDisplayMessage;
    }
  | {
      id: string;
      type: "exploration";
      messages: AgentBlockDisplayMessage[];
      summary: ExplorationSummary;
    };

type RequestPhase = "reasoning" | "content" | "tool";
type RequestSegment =
  | {
      kind: "request";
      messages: AgentBlockDisplayMessage[];
    }
  | {
      kind: "message";
      message: AgentBlockDisplayMessage;
    };

function getRequestPhase(message: AgentBlockDisplayMessage): RequestPhase | null {
  if (message.type === "reasoning") return "reasoning";
  if (message.type === "agent_output") return "content";
  if (message.type === "tool") return "tool";
  return null;
}

function isReadToolMessage(message: AgentBlockDisplayMessage): message is ToolDisplayMessage {
  return (
    message.type === "tool" && isExploreToolName(message.toolName) && message.status !== "error"
  );
}

function isToolMessage(message: AgentBlockDisplayMessage): message is ToolDisplayMessage {
  return message.type === "tool";
}

function hasPendingDisplayMessage(messages: AgentBlockDisplayMessage[]): boolean {
  return messages.some((message) =>
    Boolean(message.isStreaming || message.status === "running" || message.status === "pending"),
  );
}

function pushMessageItem(items: AgentDisplayItem[], message: AgentBlockDisplayMessage): void {
  items.push({
    id: `message:${items.length}`,
    type: "message",
    message,
  });
}

function splitAgentRequests(messages: AgentBlockDisplayMessage[]): RequestSegment[] {
  const requests: RequestSegment[] = [];
  let current: AgentBlockDisplayMessage[] = [];
  let currentPhase: RequestPhase | null = null;

  for (const message of messages) {
    if (
      message.type === "retry" ||
      message.type === "compaction" ||
      message.type === "completed" ||
      message.type === "error"
    ) {
      if (current.length > 0) {
        requests.push({ kind: "request", messages: current });
        current = [];
        currentPhase = null;
      }
      requests.push({ kind: "message", message });
      continue;
    }

    const nextPhase = getRequestPhase(message);
    if (nextPhase === null) {
      continue;
    }

    if (currentPhase !== null) {
      const phaseOrder: Record<RequestPhase, number> = {
        reasoning: 0,
        content: 1,
        tool: 2,
      };
      if (phaseOrder[nextPhase] < phaseOrder[currentPhase]) {
        requests.push({ kind: "request", messages: current });
        current = [];
        currentPhase = null;
      }
    }

    current.push(message);
    currentPhase = nextPhase;
  }

  if (current.length > 0) {
    requests.push({ kind: "request", messages: current });
  }

  return requests;
}

function pushExplorationItem(
  items: AgentDisplayItem[],
  explorationMessages: AgentBlockDisplayMessage[],
): void {
  if (explorationMessages.length === 0) return;
  const lastItem = items.at(-1);
  if (lastItem?.type === "exploration") {
    const mergedMessages = [...lastItem.messages, ...explorationMessages];
    lastItem.messages = mergedMessages;
    lastItem.summary = buildExplorationSummary(mergedMessages);
    return;
  }
  items.push({
    id: `exploration:${items.length}`,
    type: "exploration",
    messages: explorationMessages,
    summary: buildExplorationSummary(explorationMessages),
  });
}

function pushRequestItems(
  requestMessages: AgentBlockDisplayMessage[],
  items: AgentDisplayItem[],
): void {
  if (requestMessages.length === 0) return;

  const firstToolIndex = requestMessages.findIndex((message) => message.type === "tool");
  if (firstToolIndex < 0) {
    if (items.at(-1)?.type === "exploration" && hasPendingDisplayMessage(requestMessages)) {
      pushExplorationItem(items, requestMessages);
      return;
    }
    requestMessages.forEach((message) => pushMessageItem(items, message));
    return;
  }

  const firstExploreToolIndex = requestMessages.findIndex(isReadToolMessage);
  if (firstExploreToolIndex < 0) {
    requestMessages.forEach((message) => pushMessageItem(items, message));
    return;
  }

  const firstNonExploreToolIndex = requestMessages.findIndex(
    (message) => isToolMessage(message) && !isReadToolMessage(message),
  );
  const shouldGroupExplorePrefix =
    firstNonExploreToolIndex < 0 || firstExploreToolIndex < firstNonExploreToolIndex;
  if (!shouldGroupExplorePrefix) {
    requestMessages.forEach((message) => pushMessageItem(items, message));
    return;
  }

  const explorationEndIndex =
    firstNonExploreToolIndex < 0 ? requestMessages.length : firstNonExploreToolIndex;
  pushExplorationItem(items, requestMessages.slice(0, explorationEndIndex));
  requestMessages.slice(explorationEndIndex).forEach((message) => pushMessageItem(items, message));
}

export function buildExplorationSummary(messages: AgentBlockDisplayMessage[]): ExplorationSummary {
  return messages.reduce<ExplorationSummary>(
    (summary, message) => {
      if (message.type !== "tool") return summary;
      const descriptor = getToolDescriptorMeta(message.toolName);
      if (!descriptor || !descriptor.isExplore) return summary;

      if (descriptor.group === "chapter" && descriptor.tag === "read") {
        summary.chapterCount += 1;
        return summary;
      }
      if (descriptor.tag === "list") {
        summary.listCount += 1;
        return summary;
      }
      if (descriptor.group === "context") {
        summary.contextCount += 1;
        return summary;
      }
      if (descriptor.toolName.startsWith("get_") || descriptor.toolName.startsWith("read_")) {
        summary.infoCount += 1;
      }
      return summary;
    },
    {
      chapterCount: 0,
      listCount: 0,
      contextCount: 0,
      infoCount: 0,
    },
  );
}

export function formatExplorationSummary(summary: ExplorationSummary | undefined): string {
  if (!summary) return "";
  const parts: string[] = [];
  if (summary.chapterCount > 0)
    parts.push(
      i18n.t("assistant.explorationSummary.chapterCount", { count: summary.chapterCount }),
    );
  if (summary.listCount > 0)
    parts.push(i18n.t("assistant.explorationSummary.listCount", { count: summary.listCount }));
  if (summary.contextCount > 0)
    parts.push(
      i18n.t("assistant.explorationSummary.contextCount", { count: summary.contextCount }),
    );
  if (summary.infoCount > 0)
    parts.push(i18n.t("assistant.explorationSummary.infoCount", { count: summary.infoCount }));
  return parts.join(" ");
}

export function buildAgentDisplayItems(messages: AgentBlockDisplayMessage[]): AgentDisplayItem[] {
  const items: AgentDisplayItem[] = [];
  const requests = splitAgentRequests(messages);
  requests.forEach((request) => {
    if (request.kind === "message") {
      pushMessageItem(items, request.message);
      return;
    }
    pushRequestItems(request.messages, items);
  });
  return items;
}
