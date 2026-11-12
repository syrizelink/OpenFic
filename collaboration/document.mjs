import { Schema } from "@tiptap/pm/model";
import { yDocToProsemirrorJSON, prosemirrorToYXmlFragment } from "y-prosemirror";

// Matches the chapter editor exactly: one paragraph per logical line, no marks.
export const schema = new Schema({
  nodes: {
    doc: { content: "paragraph+" },
    paragraph: { content: "text*", group: "block" },
    text: { group: "inline" },
  },
});
export function seed(doc, text) {
  const node = schema.node(
    "doc",
    null,
    text
      .split("\n")
      .map((line) => schema.node("paragraph", null, line ? schema.text(line) : undefined)),
  );
  prosemirrorToYXmlFragment(node, doc.getXmlFragment("default"));
}
export function textOf(doc) {
  const json = yDocToProsemirrorJSON(doc, "default");
  return (json.content ?? [])
    .map((p) => (p.content ?? []).map((t) => t.text ?? "").join(""))
    .join("\n");
}
export function validate(doc) {
  const json = yDocToProsemirrorJSON(doc, "default");
  schema.nodeFromJSON(json).check();
  const text = textOf(doc);
  if ([...text].length > 100000 || text.split("\n").length > 2000) {
    throw new Error("Chapter content exceeds 100000 characters or 2000 lines");
  }
  return text;
}
// Map UTF-16 plaintext offsets onto the XML text nodes used by Tiptap. Preserve
// unaffected paragraphs and text identities, including the user's cursor anchors.
export function replaceRange(doc, from, to, replacement) {
  const fragment = doc.getXmlFragment("default");
  const paragraphs = fragment.toArray();
  let offset = 0;
  const locate = (position) => {
    offset = 0;
    for (let i = 0; i < paragraphs.length; i++) {
      const length = paragraphs[i].toArray().reduce((n, t) => n + t.length, 0);
      if (position <= offset + length) return { index: i, offset: position - offset };
      offset += length + 1;
    }
    throw new Error("Invalid chapter text position");
  };
  const start = locate(from),
    end = locate(to);
  // Plain chapter paragraphs contain zero or one XmlText. Normalize empty ones.
  const getText = (paragraph) => {
    if (!paragraph.length) paragraph.insert(0, [new XmlText()]);
    return paragraph.get(0);
  };
  const first = getText(paragraphs[start.index]);
  const last = getText(paragraphs[end.index]);
  const suffix = last.toString().slice(end.offset);
  const lines = replacement.split("\n");
  if (start.index === end.index && lines.length === 1) {
    first.delete(start.offset, end.offset - start.offset);
    first.insert(start.offset, replacement);
    return;
  }
  first.delete(start.offset, first.length - start.offset);
  first.insert(start.offset, lines[0]);
  if (end.index > start.index) fragment.delete(start.index + 1, end.index - start.index);
  if (lines.length === 1) {
    first.insert(first.length, suffix);
  } else {
    const added = lines.slice(1).map((line, index) => {
      const paragraph = new XmlElement("paragraph");
      const text = new XmlText();
      text.insert(0, line + (index === lines.length - 2 ? suffix : ""));
      paragraph.insert(0, [text]);
      return paragraph;
    });
    fragment.insert(start.index + 1, added);
  }
}
import { XmlElement, XmlText } from "yjs";

export function replaceExact(doc, oldText, newText, replaceAll = false) {
  if (!oldText) throw new Error("old_content must not be empty");
  const current = textOf(doc);
  const positions = [];
  for (
    let at = current.indexOf(oldText);
    at !== -1;
    at = current.indexOf(oldText, at + oldText.length)
  ) {
    positions.push(at);
  }
  if (!positions.length)
    throw new Error("Target text changed or no longer exists; read the chapter again");
  if (!replaceAll && positions.length > 1)
    throw new Error("Target text is ambiguous; include more surrounding text");
  const after = replaceAll
    ? current.split(oldText).join(newText)
    : current.replace(oldText, () => newText);
  if ([...after].length > 100000 || after.split("\n").length > 2000)
    throw new Error("Chapter content exceeds size limit");
  doc.transact(() => {
    for (const from of positions.reverse()) replaceRange(doc, from, from + oldText.length, newText);
  }, "agent");
  return { before: current, content: textOf(doc) };
}
