import type { ReasoningEffort } from "./model.types";

export const REASONING_EFFORT_VALUES: ReasoningEffort[] = [
  "auto",
  "low",
  "medium",
  "high",
  "xhigh",
  "max",
];

const REASONING_EFFORT_LABELS: Record<ReasoningEffort, string> = {
  auto: "Auto",
  low: "Low",
  medium: "Medium",
  high: "High",
  xhigh: "Xhigh",
  max: "Max",
};

export const REASONING_EFFORT_OPTIONS = REASONING_EFFORT_VALUES.map((value) => ({
  value,
  label: REASONING_EFFORT_LABELS[value],
}));

export function normalizeReasoningEffort(value: string | null | undefined): ReasoningEffort {
  if (value === "off") return "auto";
  return REASONING_EFFORT_VALUES.includes(value as ReasoningEffort)
    ? (value as ReasoningEffort)
    : "medium";
}
