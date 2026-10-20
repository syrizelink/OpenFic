import { expect, test } from "@playwright/test";

import { runUIEffects } from "../src/features/plugins/declarative-effects";

test("effects execute in order and pass results to a bounded continuation", async () => {
  const calls: string[] = [];
  const value = await runUIEffects(
    {
      effects: [{ method: "editor.insert", params: { text: "text" } }, { method: "editor.save" }],
      next: "done",
    },
    async (method) => {
      calls.push(method);
      return method === "editor.save" ? { saved: true } : undefined;
    },
    async (id, results) => {
      expect(id).toBe("done");
      expect(results).toEqual([null, { saved: true }]);
      calls.push(id);
      return { text: "Saved" };
    },
    () => true,
  );
  expect(calls).toEqual(["editor.insert", "editor.save", "done"]);
  expect(value).toEqual({ text: "Saved" });
});

test("rejects unknown methods and malformed batches before performing any effect", async () => {
  for (const result of [
    { effects: [{ method: "ui.toast" }, { method: "api.request" }] },
    { effects: [{ method: "editor.save", params: [] }] },
    { effects: Array.from({ length: 17 }, () => ({ method: "ui.toast" })) },
    { effects: [], next: 12 },
  ]) {
    let invoked = false;
    await expect(
      runUIEffects(
        result,
        async () => {
          invoked = true;
        },
        async () => null,
        () => true,
      ),
    ).rejects.toThrow();
    expect(invoked).toBe(false);
  }
});

test("capability denial or leaving a view prevents later effects and callbacks", async () => {
  let calls = 0;
  const response = {
    effects: [{ method: "editor.insert" }, { method: "editor.save" }],
    next: "done",
  };
  await expect(
    runUIEffects(
      response,
      async () => {
        calls++;
        throw new Error("Plugin has not declared editor.write");
      },
      async () => {
        throw new Error("Unexpected callback");
      },
      () => true,
    ),
  ).rejects.toThrow("editor.write");
  expect(calls).toBe(1);
  let active = true;
  calls = 0;
  await runUIEffects(
    response,
    async () => {
      calls++;
      active = false;
    },
    async () => {
      throw new Error("Unexpected callback");
    },
    () => active,
  );
  expect(calls).toBe(1);
});

test("limits recursive effects and preserves ordinary action responses", async () => {
  const result = { effects: [], next: "again" };
  let callbacks = 0;
  await expect(
    runUIEffects(
      result,
      async () => null,
      async () => {
        callbacks++;
        return result;
      },
      () => true,
    ),
  ).rejects.toThrow("chain exceeds");
  expect(callbacks).toBe(3);
  expect(
    await runUIEffects(
      { text: "normal" },
      async () => null,
      async () => null,
      () => true,
    ),
  ).toEqual({ text: "normal" });
});

test("discardResult avoids sending unnecessary editor snapshots back to the plugin", async () => {
  await runUIEffects(
    { effects: [{ method: "editor.insert", discardResult: true }], next: "done" },
    async () => ({ content: "x".repeat(100000) }),
    async (_, values) => {
      expect(values).toEqual([null]);
      return null;
    },
    () => true,
  );
});
