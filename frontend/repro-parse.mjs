import StarterKit from "@tiptap/starter-kit";
import { TableKit } from "@tiptap/extension-table";
import { TaskList, TaskItem } from "@tiptap/extension-list";
import { CodeBlockLowlight } from "@tiptap/extension-code-block-lowlight";
import { MarkdownManager } from "@tiptap/markdown";
import { createLowlight, common } from "lowlight";

// Build the same flat extension list the editor uses (minus Markdown/ui-only ones)
const extensions = [
  StarterKit.configure({ codeBlock: false }),
  TableKit,
  TaskList,
  TaskItem,
  CodeBlockLowlight.configure({ lowlight: createLowlight(common) }),
];

const manager = new MarkdownManager({ extensions });

const samples = {
  A_mixed: "# Title\n\nSome paragraph.\n\n```python\nprint('hi')\n```\n\nAfter block.",
  B_fence_only: "```python\nprint('hi')\n```",
  C_inline_code: "Just a paragraph with `inline code` and **bold**.",
  D_indented_first_doc: "before\n\n    indented code\n    line2\n\nafter",
  E_fence_with_text_after_same_line: "text\n```js\nx\n```\nmore",
};

for (const [name, md] of Object.entries(samples)) {
  let out;
  try {
    out = manager.parse(md);
  } catch (e) {
    out = "ERROR: " + e.message;
  }
  console.log("==== " + name + " ====");
  console.log(JSON.stringify(out, null, 2));
}