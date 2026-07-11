/* oxlint-disable react-refresh/only-export-components */
import { Box } from "@radix-ui/themes";
import { AudioLines, Brain, FileText, Image, Type, Video, Wrench } from "lucide-react";

import type { AvailableModel } from "@/lib/model.types";

export type ModelCapabilityKey =
  | "text"
  | "image"
  | "video"
  | "audio"
  | "pdf"
  | "reasoning"
  | "tool-call";

const MODALITY_CAPABILITY_ORDER: Array<Exclude<ModelCapabilityKey, "reasoning" | "tool-call">> = [
  "text",
  "image",
  "video",
  "audio",
  "pdf",
];

const CAPABILITY_ICON_META: Record<
  ModelCapabilityKey,
  {
    icon: typeof Type;
    color: string;
    background: string;
  }
> = {
  text: {
    icon: Type,
    color: "var(--blue-8)",
    background: "var(--blue-a3)",
  },
  image: {
    icon: Image,
    color: "var(--green-8)",
    background: "var(--green-a3)",
  },
  video: {
    icon: Video,
    color: "var(--orange-8)",
    background: "var(--orange-a3)",
  },
  audio: {
    icon: AudioLines,
    color: "var(--teal-8)",
    background: "var(--teal-a3)",
  },
  pdf: {
    icon: FileText,
    color: "var(--red-8)",
    background: "var(--red-a3)",
  },
  reasoning: {
    icon: Brain,
    color: "var(--cyan-8)",
    background: "var(--cyan-a3)",
  },
  "tool-call": {
    icon: Wrench,
    color: "var(--amber-8)",
    background: "var(--amber-a3)",
  },
};

export function getModelCapabilityKeys(
  model: Pick<AvailableModel, "inputModalities" | "reasoning" | "toolCall">,
): ModelCapabilityKey[] {
  const inputModalities = new Set(
    (model.inputModalities ?? []).map((modality) => modality.toLowerCase()),
  );
  const capabilities: ModelCapabilityKey[] = MODALITY_CAPABILITY_ORDER.filter((capability) =>
    inputModalities.has(capability),
  );

  if (model.reasoning) {
    capabilities.push("reasoning");
  }
  if (model.toolCall) {
    capabilities.push("tool-call");
  }

  return capabilities;
}

export function formatContextWindow(value: number | null | undefined): string | null {
  if (!Number.isFinite(value) || !value || value <= 0) {
    return null;
  }

  if (value >= 950_000) {
    const millions = value / 1_000_000;
    const precision = millions < 10 ? 1 : 0;
    return `${Number(millions.toFixed(precision))}M`;
  }

  if (value >= 1_000) {
    return `${Math.round(value / 1_000)}K`;
  }

  return `${Math.round(value)}`;
}

export function CapabilityIcon({ capability }: { capability: ModelCapabilityKey }) {
  const meta = CAPABILITY_ICON_META[capability];
  const Icon = meta.icon;

  return (
    <Box
      aria-hidden="true"
      style={{
        width: 18,
        height: 18,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 5,
        color: meta.color,
        background: meta.background,
        flexShrink: 0,
      }}
    >
      <Icon
        size={12}
        strokeWidth={2.2}
      />
    </Box>
  );
}

export function ContextBadge({ label }: { label: string }) {
  return (
    <Box
      style={{
        minWidth: 30,
        height: 18,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "0 7px",
        borderRadius: 5,
        color: "var(--gray-11)",
        background: "var(--gray-a3)",
        flexShrink: 0,
        fontSize: 11,
        fontWeight: 600,
        lineHeight: 1,
      }}
    >
      {label}
    </Box>
  );
}
