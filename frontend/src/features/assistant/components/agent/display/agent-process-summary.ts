import type { TFunction } from "i18next";

import { getToolDescriptorMeta } from "../message-blocks/tools/shared/tool-message-catalog";
import type { AgentBlockDisplayMessage } from "./display-message-types";

function toolActivity(toolName: string): string {
  const descriptor = getToolDescriptorMeta(toolName);
  if (toolName === "web_search") return "webSearch";
  if (toolName === "web_fetch") return "webFetch";
  if (descriptor?.group === "orchestration") return "subagents";
  if (descriptor?.group === "plan") return "plan";
  if (descriptor?.group === "interaction") return "questions";
  if (descriptor?.tag === "search" || /^(search|query)_/.test(toolName)) return "search";
  if (descriptor?.tag === "read" || /^(read|list|get)_/.test(toolName)) return "read";
  if (descriptor?.tag === "write" || /^(write|create)_/.test(toolName)) return "write";
  if (descriptor?.tag === "edit" || /^(edit|delete|move|update)_/.test(toolName)) return "edit";
  return "tools";
}

export function getLiveProcessTitleKey(messages: readonly AgentBlockDisplayMessage[]): string {
  let running: AgentBlockDisplayMessage | undefined;
  for (const message of messages) {
    if (
      message.type !== "tool" ||
      !(message.status === "running" || message.status === "pending" || message.isStreaming)
    )
      continue;
    if (!running || message.timestamp >= running.timestamp) running = message;
  }
  const activity = running?.type === "tool" ? toolActivity(running.toolName) : "thinking";
  const phase = running?.status === "pending" ? "preparing" : "running";
  return `assistant.processActivity.${phase}.${activity}`;
}

export function getCompletedProcessTitle(
  messages: readonly AgentBlockDisplayMessage[],
  t: TFunction,
): string {
  const counts = new Map<string, number>();
  const seen = new Set<string>();
  for (const message of messages) {
    if (message.type !== "tool") continue;
    const callId = message.id;
    if (seen.has(callId)) continue;
    seen.add(callId);
    const activity = toolActivity(message.toolName);
    counts.set(activity, (counts.get(activity) ?? 0) + 1);
  }
  const categories = [...counts].sort((left, right) => right[1] - left[1]);
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
