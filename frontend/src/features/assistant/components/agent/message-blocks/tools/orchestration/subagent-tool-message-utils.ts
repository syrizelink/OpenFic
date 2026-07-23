import type { AgentMessage } from "@/lib/agent.types";

import { formatSubagentDisplayLabel } from "../../../../../lib/subagent-display";
import {
  asString,
  getStreamingData,
  getToolResultData,
  isRecord,
} from "../shared/tool-message-utils";

export function getSubagentRecords(message: AgentMessage): Record<string, unknown>[] {
  const toolResult = isRecord(message.toolResult) ? message.toolResult : null;
  const resultData = getToolResultData(message);
  const records = [
    getStreamingData(message),
    message.toolArgs,
    toolResult,
    isRecord(resultData) ? resultData : null,
  ].filter((value): value is Record<string, unknown> => Boolean(value));

  const nestedRecords = records.flatMap((record) =>
    ["data", "result", "request", "metadata"].flatMap((key) => {
      const value = record[key];
      return isRecord(value) ? [value] : [];
    }),
  );

  return [...records, ...nestedRecords];
}

export function pickSubagentString(
  records: Record<string, unknown>[],
  keys: string[],
): string | undefined {
  for (const record of records) {
    for (const key of keys) {
      const value = asString(record[key]);
      if (value) return value;
    }
  }
  return undefined;
}

export function pickSubagentBoolean(
  records: Record<string, unknown>[],
  keys: string[],
): boolean | undefined {
  for (const record of records) {
    for (const key of keys) {
      const value = record[key];
      if (typeof value === "boolean") return value;
    }
  }
  return undefined;
}

export function getSubagentTargetLabel(message: AgentMessage): string {
  const records = getSubagentRecords(message);
  const agentKey = pickSubagentString(records, [
    "agent_key",
    "agent",
    "agent_name",
    "target_agent",
    "agent_type",
  ]);
  const agentNumber = pickSubagentString(records, ["agent_number"]);
  return formatSubagentDisplayLabel(agentKey, agentNumber);
}

export function getSubagentInstructionText(
  message: AgentMessage,
  keys: string[],
): string | undefined {
  return pickSubagentString(getSubagentRecords(message), keys);
}
