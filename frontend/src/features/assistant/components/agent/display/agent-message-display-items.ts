import type { AgentBlockDisplayMessage } from "./display-message-types";

export type AgentDisplayItem =
  | { id: string; type: "message"; message: AgentBlockDisplayMessage }
  | {
      id: string;
      type: "process";
      kind: "simple" | "subagent";
      messages: AgentBlockDisplayMessage[];
    };

export function isAgentProcessMessage(message: { type: string }): boolean {
  return message.type === "reasoning" || message.type === "tool" || message.type === "retry";
}

export function buildAgentDisplayItems(
  messages: AgentBlockDisplayMessage[],
  previousItems: AgentDisplayItem[] = [],
): AgentDisplayItem[] {
  const items: AgentDisplayItem[] = [];
  for (const message of messages) {
    if (message.type === "agent_output" && !message.content?.trim()) continue;
    if (!isAgentProcessMessage(message)) {
      items.push({ id: `message:${message.id}`, type: "message", message });
      continue;
    }
    const lastItem = items.at(-1);
    if (message.type === "tool" && message.toolName === "dispatch_subagent") {
      const reasoning: AgentBlockDisplayMessage[] = [];
      if (lastItem?.type === "process" && lastItem.kind === "simple") {
        const reasoningStart =
          lastItem.messages.findLastIndex((item) => item.type !== "reasoning") + 1;
        reasoning.push(...lastItem.messages.splice(reasoningStart));
        if (lastItem.messages.length === 0) items.pop();
      }
      items.push({
        id: `process:${reasoning[0]?.id ?? message.id}`,
        type: "process",
        kind: "subagent",
        messages: [...reasoning, message],
      });
    } else if (lastItem?.type === "process" && lastItem.kind === "simple")
      lastItem.messages.push(message);
    else
      items.push({
        id: `process:${message.id}`,
        type: "process",
        kind: "simple",
        messages: [message],
      });
  }

  const previousIds = new Map(
    previousItems
      .filter((item) => item.type === "process")
      .flatMap((item) => item.messages.map((message) => [message.id, item.id] as const)),
  );
  const usedIds = new Set<string>();
  for (const item of items) {
    if (item.type !== "process") continue;
    const previousId = item.messages
      .map((message) => previousIds.get(message.id))
      .find((id) => id !== undefined && !usedIds.has(id));
    if (previousId) item.id = previousId;
    usedIds.add(item.id);
  }
  return items;
}
