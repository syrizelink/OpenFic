import type { TFunction } from "i18next";

import { getToolDescriptorMeta } from "../message-blocks/tools/shared/tool-message-catalog";
import type { AgentBlockDisplayMessage } from "./display-message-types";

export type ProcessActivity =
  | "thinking"
  | "read"
  | "search"
  | "edit"
  | "webSearch"
  | "webFetch"
  | "subagents"
  | "skills"
  | "plan"
  | "questions"
  | "tools";

function toolActivity(toolName: string): ProcessActivity {
  const descriptor = getToolDescriptorMeta(toolName);
  if (toolName === "web_search") return "webSearch";
  if (toolName === "web_fetch") return "webFetch";
  if (descriptor?.group === "orchestration") return "subagents";
  if (descriptor?.group === "plan") return "plan";
  if (descriptor?.group === "interaction") return "questions";
  if (toolName === "activate_skill" || toolName === "reference_skill") return "skills";
  if (descriptor?.tag === "search" || /^(search|query)_/.test(toolName)) return "search";
  if (descriptor?.tag === "read" || /^(read|list|get)_/.test(toolName)) return "read";
  if (
    descriptor?.tag === "write" ||
    descriptor?.tag === "edit" ||
    /^(write|create|edit|delete|move|update)_/.test(toolName)
  )
    return "edit";
  return "tools";
}

function getLiveProcessMessage(
  messages: readonly AgentBlockDisplayMessage[],
): Extract<AgentBlockDisplayMessage, { type: "tool" }> | undefined {
  let running: AgentBlockDisplayMessage | undefined;
  for (const message of messages) {
    if (
      message.type !== "tool" ||
      !(message.status === "running" || message.status === "pending" || message.isStreaming)
    )
      continue;
    if (!running || message.timestamp >= running.timestamp) running = message;
  }
  return running?.type === "tool" ? running : undefined;
}

export function getLiveProcessActivity(
  messages: readonly AgentBlockDisplayMessage[],
): ProcessActivity {
  const running = getLiveProcessMessage(messages);
  return running ? toolActivity(running.toolName) : "thinking";
}

export function getLiveProcessTitleKey(messages: readonly AgentBlockDisplayMessage[]): string {
  const activity = getLiveProcessActivity(messages);
  const running = getLiveProcessMessage(messages);
  const phase = running?.status === "pending" ? "preparing" : "running";
  return `assistant.processActivity.${phase}.${activity}`;
}

function getCompletedProcessCategories(
  messages: readonly AgentBlockDisplayMessage[],
): Array<[ProcessActivity, number]> {
  const counts = new Map<ProcessActivity, number>();
  const seen = new Set<string>();
  for (const message of messages) {
    if (message.type !== "tool") continue;
    const callId = message.id;
    if (seen.has(callId)) continue;
    seen.add(callId);
    const activity = toolActivity(message.toolName);
    counts.set(activity, (counts.get(activity) ?? 0) + 1);
  }
  return [...counts].sort((left, right) => right[1] - left[1]);
}

export function getCompletedProcessActivity(
  messages: readonly AgentBlockDisplayMessage[],
): ProcessActivity {
  return getCompletedProcessCategories(messages)[0]?.[0] ?? "thinking";
}

export function getCompletedProcessTitle(
  messages: readonly AgentBlockDisplayMessage[],
  t: TFunction,
): string {
  const categories = getCompletedProcessCategories(messages);
  const labels = categories
    .slice(0, 3)
    .map(([activity]) => t(`assistant.processActivity.completed.${activity}`));
  const first = labels[0];
  if (!first) return t("assistant.processActivity.completed.thinking");
  const second = labels[1];
  if (!second) return first;
  const continuation = (label: string) => label.charAt(0).toLowerCase() + label.slice(1);
  if (labels.length === 2) {
    const prefix = t("assistant.processActivity.sharedPrefix");
    const sharedPrefix = prefix !== "" && first.startsWith(prefix) && second.startsWith(prefix);
    return t("assistant.processActivity.joinTwo", {
      first,
      second: continuation(sharedPrefix ? second.slice(prefix.length) : second),
    });
  }
  const title = [first, ...labels.slice(1).map(continuation)].join(
    t("assistant.processActivity.comma"),
  );
  return categories.length > 3 ? t("assistant.processActivity.more", { title }) : title;
}

export function getTurnProcessTitle(elapsedMs: number | undefined, t: TFunction): string {
  if (elapsedMs === undefined || !Number.isFinite(elapsedMs) || elapsedMs < 0)
    return t("assistant.turnProcessCompleted");
  const totalSeconds = Math.max(1, Math.floor(elapsedMs / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor(totalSeconds / 60) % 60;
  const seconds = totalSeconds % 60;
  const duration = t(
    `assistant.processDuration.${hours > 0 ? "hours" : totalSeconds >= 60 ? "minutes" : "seconds"}`,
    {
      hours,
      minutes,
      seconds,
    },
  );
  return t("assistant.turnProcessCompletedIn", { duration });
}
