import assert from "node:assert/strict";
import test from "node:test";
import * as Y from "yjs";
import { schema, seed, textOf, replaceExact, validate } from "../document.mjs";
import { prosemirrorToYXmlFragment } from "y-prosemirror";

function document(text) {
  const doc = new Y.Doc();
  seed(doc, text);
  return doc;
}

test("Agent edit and simultaneous typing at the end converge without losing either edit", () => {
  const server = document("Sunny morning\nThe end");
  const human = new Y.Doc();
  Y.applyUpdate(human, Y.encodeStateAsUpdate(server));
  const agent = new Y.Doc();
  Y.applyUpdate(agent, Y.encodeStateAsUpdate(server));
  const paragraph = human.getXmlFragment("default").get(1).get(0);
  paragraph.insert(paragraph.length, " and a bell");
  replaceExact(agent, "Sunny morning", "Rain everywhere");
  Y.applyUpdate(server, Y.encodeStateAsUpdate(human));
  Y.applyUpdate(server, Y.encodeStateAsUpdate(agent));
  Y.applyUpdate(human, Y.encodeStateAsUpdate(server));
  assert.equal(textOf(server), "Rain everywhere\nThe end and a bell");
  assert.equal(textOf(human), textOf(server));
});

test("multiline replacements preserve untouched paragraph identities and whitespace", () => {
  const doc = document("  one\ntwo\nthree\n untouched  \n");
  const untouched = doc.getXmlFragment("default").get(3);
  replaceExact(doc, "one\ntwo\nthree", "first\nsecond");
  assert.equal(textOf(doc), "  first\nsecond\n untouched  \n");
  assert.equal(doc.getXmlFragment("default").get(2), untouched);
  validate(doc);
});

test("inserting newline into a paragraph and deleting newline use valid Tiptap XML", () => {
  const doc = document("before middle after");
  replaceExact(doc, "middle", "new\nparagraph");
  assert.equal(textOf(doc), "before new\nparagraph after");
  replaceExact(doc, "new\nparagraph", "middle");
  assert.equal(textOf(doc), "before middle after");
  validate(doc);
});

test("binary restart retains history, blank lines, Unicode and literal HTML characters", () => {
  const doc = document("甲🙂 & <tag>\n\n尾\n");
  replaceExact(doc, "甲🙂 & <tag>", "乙🙂 & <new>");
  const recovered = new Y.Doc();
  Y.applyUpdate(recovered, Y.encodeStateAsUpdate(doc));
  assert.equal(textOf(recovered), "乙🙂 & <new>\n\n尾\n");
  replaceExact(recovered, "尾", "新的尾");
  Y.applyUpdate(doc, Y.encodeStateAsUpdate(recovered));
  assert.equal(textOf(doc), "乙🙂 & <new>\n\n新的尾\n");
});

test("stale, ambiguous and oversized edits leave the document untouched", () => {
  const doc = document("same\nsame");
  for (const edit of [
    ["missing", "x"],
    ["same", "x"],
    ["same\nsame", "x".repeat(100001)],
  ]) {
    assert.throws(() => replaceExact(doc, ...edit));
    assert.equal(textOf(doc), "same\nsame");
  }
  replaceExact(doc, "same", "different", true);
  assert.equal(textOf(doc), "different\ndifferent");
});

test("ProseMirror XML can be edited without rebuilding the full document", () => {
  const doc = new Y.Doc();
  prosemirrorToYXmlFragment(
    schema.nodeFromJSON({
      type: "doc",
      content: [{ type: "paragraph", content: [{ type: "text", text: "a < b & c" }] }],
    }),
    doc.getXmlFragment("default"),
  );
  replaceExact(doc, "< b &", "> d &");
  assert.equal(textOf(doc), "a > d & c");
});
