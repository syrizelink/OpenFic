import { getTextBetween, getTextSerializersFromSchema, type JSONContent } from "@tiptap/core";
import type { MarkdownManager } from "@tiptap/markdown";
import type { Fragment, Schema } from "@tiptap/pm/model";

export function serializeClipboardText(content: Fragment, schema: Schema): string {
  const document = schema.topNodeType.create(null, content);

  return getTextBetween(
    document,
    { from: 0, to: document.content.size },
    { blockSeparator: "\n", textSerializers: getTextSerializersFromSchema(schema) },
  );
}

export function serializeClipboardMarkdown(
  markdown: MarkdownManager,
  content: JSONContent,
): string {
  const nodes = content.content ?? [];

  return nodes
    .map((node, index) => {
      const separator =
        index === 0 || (node.type === "paragraph" && nodes[index - 1]?.type === "paragraph")
          ? ""
          : "\n";
      return `${separator}${markdown.serialize({ type: "doc", content: [node] })}`;
    })
    .join("\n");
}
