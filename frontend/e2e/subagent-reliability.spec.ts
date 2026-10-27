import { expect, test } from "@playwright/test";

import {
  call,
  checked,
  control,
  dispatch,
  scenario,
  seed,
  toolResult,
  type Scenario,
} from "./background-subagents.helpers";
import { sendMessage } from "./helpers";

test.describe("Subagent 可靠性修复", () => {
  let current: Scenario | undefined;
  let browserErrors: string[];
  test.beforeAll(async ({ request }) => {
    await seed(request);
  });
  test.beforeEach(async ({ page }) => {
    current = undefined;
    browserErrors = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));
  });
  test.afterEach(async ({ page }, info) => {
    await checked(page.request, "POST", `${control}/board-notice-failure`, { enabled: false });
    if (current?.sessionId) {
      await info.attach("runtime-state", {
        body: JSON.stringify(await current.state(), null, 2),
        contentType: "application/json",
      });
      await current.cancel();
      expect((await current.state()).checkpoint_errors).toEqual([]);
    }
    expect(browserErrors).toEqual([]);
  });

  test("重放同一通知工具调用只执行一次，复用请求和后台报告", async ({ page }) => {
    const notification = call("same-notify", "notify_subagent", {
      dispatch_id: "$dispatch:one",
      prompt: "第二轮原文 🌙",
      background: true,
    });
    current = await scenario(page, {
      parent: [
        { tools: [dispatch("one", false)] },
        { tools: [notification] },
        { until_results: 1, tools: [notification] },
        { text: "E2E_DONE" },
      ],
      children: { one: [{ text: "FIRST" }, { text: "SECOND" }] },
    });
    await current.start();
    const done = await current.finish();
    expect(done.children).toHaveLength(1);
    expect(done.requests).toHaveLength(2);
    expect(done.calls.filter((item) => item.actor === "one")).toHaveLength(2);
    expect(done.messages.filter((item) => item.message_type === "subagent_result")).toHaveLength(1);
  });

  test("跨两轮派发最多占用十个名额，完成一个后可派发替补", async ({ page }) => {
    test.setTimeout(120_000);
    const labels = Array.from({ length: 12 }, (_, i) => `child-${i}`);
    current = await scenario(page, {
      parent: [
        { tools: labels.slice(0, 6).map((label) => dispatch(label)) },
        { tools: labels.slice(6).map((label) => dispatch(label)) },
        { gate: "parent-check", tools: [call("independent", "list_notes")] },
        { tools: [dispatch("replacement")] },
        { until_results: 11, text: "E2E_DONE" },
      ],
      children: {
        ...Object.fromEntries(
          labels.map((label, i) => [label, [{ gate: `hold-${i}`, text: `DONE_${i}` }]]),
        ),
        replacement: [{ text: "REPLACEMENT_DONE" }],
      },
    });
    await current.start();
    const full = await current.until(
      (state) => state.calls.some((item) => item.actor === "parent" && item.step === 2),
      "十个后台子代理就绪且超额派发已拒绝",
      40_000,
    );
    expect(full.children).toHaveLength(10);
    expect(full.requests).toHaveLength(10);
    expect(full.children.every((child) => child.runtime_running)).toBe(true);
    for (const label of labels.slice(10)) {
      expect(toolResult(full, label).success).toBe(false);
      expect(toolResult(full, label).code).toBe("limit_exceeded");
      expect(JSON.stringify(toolResult(full, label))).toContain("active subagents");
    }
    await current.release("hold-0");
    await current.until((state) =>
      state.children.some((child) => child.status === "completed" && !child.runtime_running),
    );
    await current.release("parent-check");
    const replaced = await current.until((state) => state.children.length === 11);
    expect(toolResult(replaced, "replacement").success).not.toBe(false);
    expect(replaced.children.filter((child) => child.runtime_running).length).toBeLessThanOrEqual(
      10,
    );
    for (let i = 1; i < 10; i++) await current.release(`hold-${i}`);
    expect((await current.finish()).requests).toHaveLength(11);
  });

  test("通知空闲子代理也须取得名额，超限不会留下通知请求", async ({ page }) => {
    test.setTimeout(120_000);
    const labels = Array.from({ length: 10 }, (_, i) => `busy-${i}`);
    const notify = (id: string) =>
      call(id, "notify_subagent", {
        dispatch_id: "$dispatch:idle",
        prompt: "继续处理",
        background: true,
      });
    current = await scenario(page, {
      parent: [
        { tools: [dispatch("idle", false)] },
        { gate: "idle-exited", tools: labels.map((label) => dispatch(label)) },
        { tools: [notify("blocked-notify")] },
        { gate: "parent-check", tools: [call("independent", "list_notes")] },
        { tools: [notify("accepted-notify")] },
        { until_results: 11, text: "E2E_DONE" },
      ],
      children: {
        idle: [{ text: "IDLE" }, { text: "CONTINUED" }],
        ...Object.fromEntries(
          labels.map((label, i) => [label, [{ gate: `hold-${i}`, text: `DONE_${i}` }]]),
        ),
      },
    });
    await current.start();
    await current.until((state) =>
      state.children.some((child) => child.status === "completed" && !child.runtime_running),
    );
    await current.release("idle-exited");
    const blocked = await current.until(
      (state) => state.calls.some((item) => item.actor === "parent" && item.step === 3),
      "十个后台子代理就绪且空闲通知已拒绝",
      40_000,
    );
    expect(toolResult(blocked, "blocked-notify").success).toBe(false);
    expect(toolResult(blocked, "blocked-notify").code).toBe("limit_exceeded");
    expect(blocked.requests).toHaveLength(11);
    expect(blocked.calls.filter((item) => item.actor === "idle")).toHaveLength(1);
    await current.release("hold-0");
    await current.until(
      (state) =>
        state.children.filter((child) => child.status === "completed" && !child.runtime_running)
          .length >= 2,
    );
    await current.release("parent-check");
    await current.until((state) => state.requests.length === 12);
    for (let i = 1; i < 10; i++) await current.release(`hold-${i}`);
    const done = await current.finish();
    expect(done.calls.filter((item) => item.actor === "idle")).toHaveLength(2);
    expect(done.requests).toHaveLength(12);
  });

  test("看板提醒查询失败仍正常推理和调用工具，恢复后重新注入正常说明", async ({ page }) => {
    current = await scenario(page, {
      parent: [
        { tools: [call("notes", "list_notes")] },
        { text: "E2E_DONE" },
        { tools: [call("notes-recovered", "list_notes")] },
        { text: "RECOVERED_DONE" },
      ],
      children: {},
    });
    await checked(page.request, "POST", `${control}/board-notice-failure`, { enabled: true });
    await current.start();
    const degraded = await current.finish();
    expect(toolResult(degraded, "notes").success).not.toBe(false);
    expect(JSON.stringify(degraded.calls[0].messages)).toContain("协作提醒暂不可用");
    await checked(page.request, "POST", `${control}/board-notice-failure`, { enabled: false });
    await sendMessage(page, `E2E_SCENARIO:${current.id} 恢复后继续。`);
    const restored = await current.finish("RECOVERED_DONE");
    expect(JSON.stringify(restored.calls.at(-1)?.messages)).not.toContain("协作提醒暂不可用");
    expect(JSON.stringify(restored.calls.at(-1)?.messages)).toContain("你的看板身份：main");
  });
});
