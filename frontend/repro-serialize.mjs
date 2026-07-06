import { CodeBlockLowlight } from "@tiptap/extension-code-block-lowlight";
import { MarkdownManager } from "@tiptap/markdown";
// Minimal manager: only needs render handlers for serialize. Register a tiny set
// by constructing with empty extensions then rely on fallback renderers? The
// fallback renderMarkdown only exists for registered nodes. So we must register
// real extensions. Reuse the real set:
import StarterKit from "@tiptap/starter-kit";
import { createLowlight, common } from "lowlight";

const manager = new MarkdownManager({
  extensions: [
    StarterKit.configure({ codeBlock: false }),
    CodeBlockLowlight.configure({ lowlight: createLowlight(common) }),
  ],
});

const doc = {
  type: "doc",
  content: [
    { type: "paragraph", content: [{ type: "text", text: "Before block." }] },
    {
      type: "codeBlock",
      attrs: { language: "python" },
      content: [{ type: "text", text: "print('hi')" }],
    },
    { type: "paragraph", content: [{ type: "text", text: "After block." }] },
  ],
};

console.log("==== serialize [para, codeBlock, para] ====");
console.log(JSON.stringify(manager.serialize(doc)));
console.log("---- raw repr ----");
console.log(manager.serialize(doc));

// Also: a slice that starts mid-codeBlock (content begins with the code block)
const sliceStartsAtCode = {
  type: "doc",
  content: [
    {
      type: "codeBlock",
      attrs: { language: "python" },
      content: [{ type: "text", text: "print('hi')" }],
    },
    { type: "paragraph", content: [{ type: "text", text: "After block." }] },
  ],
};
console.log("\n==== serialize [codeBlock, para] ====");
console.log(manager.serialize(sliceStartsAtCode));
