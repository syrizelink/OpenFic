import type { AgentMessage } from "@/lib/agent.types";

export function getLatestUserPrompt(messages: AgentMessage[]): string | undefined {
  const message = messages.findLast(
    (item) =>
      item.role === "user" &&
      (item.type === "text" || item.type === "user_request") &&
      item.payload?.kind !== "question_answer" &&
      item.content?.trim(),
  );
  return message?.content?.trim();
}

export function getLastAssistantOutput(messages: AgentMessage[]): string | undefined {
  const lastUserIndex = messages.findLastIndex(
    (item) =>
      item.role === "user" &&
      (item.type === "text" || item.type === "user_request") &&
      item.payload?.kind !== "question_answer",
  );
  const currentTurn = messages.slice(lastUserIndex + 1);
  const output = currentTurn.findLast(
    (item) =>
      ((item.type === "text" && item.role === "assistant") || item.type === "agent_output") &&
      item.content?.trim(),
  );
  return (
    output?.content?.trim() ||
    currentTurn.findLast((item) => item.type === "completed")?.finalContent?.trim()
  );
}

export function getQuestionNotificationBody(questions: Array<{ title: string }>): string {
  return questions
    .map((question) => question.title.trim())
    .filter(Boolean)
    .map((title, index) => `${index + 1}. ${title}`)
    .join("\n");
}

export function shouldShowAgentNotification(
  enabled: boolean,
  onlyWhenUnfocused: boolean,
  isFocused: boolean,
): boolean {
  return enabled && (!onlyWhenUnfocused || !isFocused);
}

export type AgentNotificationType = "completed" | "approval" | "question";

export function isTerminalAgentError(previousStatus: string, nextStatus: string): boolean {
  return (
    nextStatus === "error" &&
    (previousStatus === "running" ||
      previousStatus === "waiting_approval" ||
      previousStatus === "waiting_answer")
  );
}

export function getAgentNotificationType(
  eventType: string,
  previousStatus: string,
  nextStatus: string,
  previousMessages: AgentMessage[],
  message: AgentMessage | null,
): AgentNotificationType | null {
  if (eventType === "task_completed" && previousStatus === "running" && nextStatus === "completed")
    return "completed";
  if (
    eventType === "approval" &&
    nextStatus === "waiting_approval" &&
    message?.type === "approval" &&
    message.status === "pending" &&
    !previousMessages.some(
      (item) =>
        item.type === "approval" &&
        (message.interruptBatchId
          ? item.interruptBatchId === message.interruptBatchId
          : item.id === message.id),
    )
  )
    return "approval";
  if (
    eventType === "question" &&
    previousStatus !== "waiting_answer" &&
    nextStatus === "waiting_answer"
  )
    return "question";
  return null;
}
