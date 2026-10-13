import { test } from "node:test";
import assert from "node:assert/strict";
import { normalizeInstanceUrl, readInstances } from "../src/instances.mjs";
test("normalizes remote and LAN origins", () => {
  assert.equal(normalizeInstanceUrl(" https://Example.com:443/ "), "https://example.com");
  assert.equal(normalizeInstanceUrl("http://192.168.1.20:8000/"), "http://192.168.1.20:8000");
  assert.equal(normalizeInstanceUrl("http://[2001:db8::1]:8000"), "http://[2001:db8::1]:8000");
});
test("rejects local instances, credentials and non-root URLs", () => {
  for (const input of [
    "http://localhost",
    "http://127.1",
    "http://127.0.0.1",
    "http://[::1]",
    "http://0.0.0.0",
    "file:///tmp",
    "https://user:pass@example.com",
    "https://example.com/api",
    "https://example.com?token=secret",
    "https://example.com#foo",
    "example.com",
  ])
    assert.throws(() => normalizeInstanceUrl(input), input);
});
test("corrupt saved configuration does not break startup", () => {
  assert.deepEqual(readInstances({ getItem: () => "{invalid" }), []);
  assert.deepEqual(readInstances({ getItem: () => "{}" }), []);
  const valid = { id: "1", name: "My server", url: "https://example.com" };
  assert.deepEqual(
    readInstances({
      getItem: () => JSON.stringify([null, {}, valid, { ...valid, url: "http://localhost" }]),
    }),
    [valid],
  );
});
