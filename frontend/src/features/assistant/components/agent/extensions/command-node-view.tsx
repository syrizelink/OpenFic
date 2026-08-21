import { NodeViewWrapper, type NodeViewProps } from "@tiptap/react";

import {
  getCommandDisplayLabel,
  type AssistantCommandKind,
  type AssistantCommandToken,
} from "@/features/assistant/lib/command-text";

import { MentionChip } from "../mention-chip";

export function CommandNodeView({ node, selected }: NodeViewProps) {
  const kind = (node.attrs.commandKind ?? "skill") as AssistantCommandKind;
  const token: AssistantCommandToken = {
    markup: "command",
    raw: String(node.attrs.commandRaw ?? ""),
    kind,
    attrs: {
      id: String(node.attrs.commandId ?? ""),
      name: String(node.attrs.commandName ?? ""),
    },
    body: "",
  };

  return (
    <NodeViewWrapper
      as="span"
      data-command-kind={kind}
      draggable={false}
    >
      <MentionChip
        kind={kind}
        label={getCommandDisplayLabel(token)}
        selected={selected}
      />
    </NodeViewWrapper>
  );
}
