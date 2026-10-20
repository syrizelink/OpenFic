import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Page, type APIRequestContext } from "@playwright/test";

const backend = process.env.OPENFIC_E2E_BACKEND ?? "http://127.0.0.1:8031";
const api = backend + "/api/v1";
const root = fileURLToPath(new URL("../../", import.meta.url));
test.use({ video: "off", hasTouch: true });

async function checked(response: Awaited<ReturnType<APIRequestContext["post"]>>) {
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}
async function storage(page: Page) {
  return (
    await checked(
      await page.request.post(`${api}/plugins/deepseek-whale/rpc`, {
        data: { method: "sdk.storage.get", params: { key: "whale.state.v1", default: {} } },
      }),
    )
  ).result;
}
async function install(page: Page) {
  await page.request.delete(`${api}/plugins/deepseek-whale`);
  await page.goto("/extensions");
  await page.getByRole("checkbox").check();
  await page
    .locator('input[type="file"]')
    .setInputFiles(root + "examples/plugins/dist/deepseek-whale-1.0.0.zip");
  const card = page.locator('[data-plugin-id="deepseek-whale"]');
  await expect(card).toBeVisible();
  await checked(
    await page.request.put(`${api}/plugins/deepseek-whale/settings`, {
      data: { settings: { apiKey: "whale-test-main", budget: 5, lowBalance: 5 } },
    }),
  );
  return card;
}

// Test routes use fake providers; all installation, persistence, UI and Agent work is real.
test("native whale: installs, balances/credits/stale/correction, dragging, preferences, mobile and independent overlays", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await checked(
    await page.request.post(`${backend}/_e2e/whale/balance`, {
      data: { total: "100", status: 200, currency: "CNY" },
    }),
  );
  const project = await checked(
    await page.request.post(`${api}/projects`, { multipart: { title: "小鲸鱼移植验证" } }),
  );
  try {
    await install(page);
    const volume = (
      await (await page.request.get(`${api}/projects/${project.id}/volumes`)).json()
    )[0];
    const chapter = await checked(
      await page.request.post(`${api}/projects/${project.id}/chapters`, {
        data: {
          title: "浮层不会挤占编辑器",
          volume_id: volume.id,
          content: "仍然可以写作。",
          word_count: 7,
        },
      }),
    );
    await page.goto(`/projects/${project.id}`);
    await page.getByText("浮层不会挤占编辑器", { exact: true }).first().click();
    const content = page.locator(".chapter-editor-content .tiptap");
    await expect(content).toHaveText("仍然可以写作。");
    const before = await page.locator(".tiptap-editor-wrapper").boundingBox();
    await checked(
      await page.request.patch(`${api}/plugins/deepseek-whale/enabled`, {
        data: { enabled: true },
      }),
    );
    const widget = page.locator('[data-plugin-view="deepseek-whale/widget"]');
    const panel = widget.locator(".plugin-floating-panel");
    await expect(widget.getByRole("img", { name: "DeepSeek 小鲸鱼" })).toBeVisible();
    await expect(widget.getByRole("img")).toHaveJSProperty("naturalWidth", 610);
    await expect(widget.locator("iframe")).toHaveCount(0);
    expect(await page.locator(".tiptap-editor-wrapper").boundingBox()).toEqual(before);
    await content.fill("悬浮挂件存在时，正文仍能编辑并保存。");
    await content.press("Control+s");
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${api}/chapters/${chapter.id}`)).json()).content,
      )
      .toContain("正文仍能编辑并保存");
    await widget.getByRole("button", { name: "刷新余额", exact: true }).click();
    await expect(widget.locator("#whale-balance")).toHaveText("余额 CNY 100.00");
    await checked(
      await page.request.post(`${backend}/_e2e/whale/balance`, { data: { total: "90" } }),
    );
    await widget.getByRole("button", { name: "刷新余额", exact: true }).click();
    await expect(widget).toContainText("今日观测 CNY 10.00");
    await checked(
      await page.request.post(`${backend}/_e2e/whale/balance`, { data: { total: "120" } }),
    );
    await widget.getByRole("button", { name: "刷新余额", exact: true }).click();
    await expect(widget.locator("#whale-balance")).toHaveText("余额 CNY 120.00");
    await expect(widget).toContainText("今日观测 CNY 10.00");
    await checked(
      await page.request.post(`${backend}/_e2e/whale/balance`, { data: { status: 503 } }),
    );
    await widget.getByRole("button", { name: "刷新余额", exact: true }).click();
    await expect(widget).toContainText("余额已过期");
    await expect(widget.locator("#whale-balance")).toHaveText("余额 CNY 120.00");
    await widget.getByRole("button", { name: "戳一下小鲸鱼" }).click();
    await expect(widget).toContainText("小鲸鱼帮你看着余额。");
    const handle = widget.getByRole("button", { name: "移动小鲸鱼" });
    const initial = (await handle.boundingBox())!;
    await page.mouse.move(initial.x + initial.width / 2, initial.y + initial.height / 2);
    await page.mouse.down();
    await page.mouse.move(initial.x - 120, initial.y - 80, { steps: 8 });
    await page.mouse.up();
    await expect.poll(async () => (await storage(page)).position?.x).toBeLessThan(1300);
    const savedPosition = (await storage(page)).position;
    await page.reload();
    await expect(panel).toBeVisible();
    await expect.poll(async () => (await panel.boundingBox())?.x).toBeCloseTo(savedPosition.x, 0);
    await handle.focus();
    await handle.press("ArrowLeft");
    await expect
      .poll(async () => (await storage(page)).position?.x)
      .toBeCloseTo(savedPosition.x - 10, 0);
    await page.screenshot({ path: info.outputPath("whale-desktop.png"), animations: "disabled" });
    await widget.getByRole("button", { name: "小鲸鱼设置" }).click();
    const settings = page.locator('[data-plugin-view="deepseek-whale/settings"]');
    await expect(settings.locator("#observed")).toHaveText("CNY 10.00");
    await expect(settings).toContainText("增加 30.00000000");
    await settings
      .getByLabel("气泡台词（每行一句）")
      .fill("原生 SDK 也可以实现悬浮挂件。\n第二条台词");
    await expect
      .poll(async () => (await storage(page)).phrases)
      .toEqual(["原生 SDK 也可以实现悬浮挂件。", "第二条台词"]);
    await checked(
      await page.request.post(`${backend}/_e2e/whale/balance`, { data: { status: 200 } }),
    );
    await settings.getByLabel("今日消费校正值").fill("17.50");
    await settings.getByRole("button", { name: "保存今日校正" }).click();
    await expect(settings.locator("#status")).toHaveText("今日校正已保存");
    await expect(settings.locator("#observed")).toHaveText("CNY 17.50");
    await settings.getByRole("slider", { name: "角色大小" }).focus();
    await settings.getByRole("slider", { name: "角色大小" }).press("ArrowRight");
    await expect.poll(async () => (await storage(page)).size).toBe(172);
    await page.screenshot({ path: info.outputPath("whale-settings.png"), animations: "disabled" });
    await widget.getByRole("button", { name: "隐藏挂件" }).click();
    await expect(panel).not.toBeVisible();
    await settings.getByRole("button", { name: "显示挂件", exact: true }).click();
    await expect(panel).toBeVisible();
    // Secret-only config updates refresh the native view without disclosing the key.
    await checked(
      await page.request.put(`${api}/plugins/deepseek-whale/settings`, {
        data: { settings: { apiKey: "whale-test-other" } },
      }),
    );
    await expect(settings).toContainText("账户已变更");
    await expect(settings.locator("#balance")).toHaveText("—");
    expect(await settings.textContent()).not.toContain("whale-test-other");
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await expect(panel).toBeVisible();
    const mobile = (await panel.boundingBox())!;
    expect(mobile.x).toBeGreaterThanOrEqual(0);
    expect(mobile.x + mobile.width).toBeLessThanOrEqual(390);
    const h = (await handle.boundingBox())!;
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Input.dispatchTouchEvent", {
      type: "touchStart",
      touchPoints: [{ x: h.x + h.width / 2, y: h.y + h.height / 2 }],
    });
    await cdp.send("Input.dispatchTouchEvent", {
      type: "touchMove",
      touchPoints: [{ x: h.x + h.width / 2 - 40, y: h.y + h.height / 2 - 50 }],
    });
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await expect.poll(async () => (await panel.boundingBox())?.x).toBeLessThan(mobile.x);
    await cdp.detach();
    await page.screenshot({ path: info.outputPath("whale-mobile.png"), animations: "disabled" });
    // A second native plugin uses the same generic SDK; no whale-specific host hooks.
    const zip = "/tmp/openfic-overlay-probe.zip";
    execFileSync("python3", [
      root + "examples/plugins/build_package.py",
      root + "frontend/e2e/fixtures/plugin-overlay-probe",
      zip,
    ]);
    await checked(
      await page.request.post(`${api}/plugins`, {
        multipart: {
          trusted: "true",
          file: { name: "probe.zip", mimeType: "application/zip", buffer: readFileSync(zip) },
        },
      }),
    );
    await checked(
      await page.request.patch(`${api}/plugins/overlay-probe/enabled`, { data: { enabled: true } }),
    );
    const probe = page.locator('[data-plugin-view="overlay-probe/panel"]');
    await expect(probe).toContainText("独立浮层探针");
    await probe.getByLabel("探针输入").fill("<script>plain text</script>");
    await expect(probe.locator("#echo")).toHaveText("<script>plain text</script>");
    await expect(probe.locator("svg script,script")).toHaveCount(0);
    await expect(probe.getByRole("img", { name: "拒绝 SVG" })).toHaveAttribute(
      "title",
      "Image unavailable",
    );
    await checked(
      await page.request.patch(`${api}/plugins/deepseek-whale/enabled`, {
        data: { enabled: false },
      }),
    );
    await expect(widget).toHaveCount(0);
    await expect(probe.locator(".plugin-floating-panel")).toBeVisible();
    expect(errors).toEqual([]);
  } finally {
    await Promise.allSettled([
      page.request.delete(`${api}/plugins/overlay-probe`),
      page.request.delete(`${api}/plugins/deepseek-whale`),
      page.request.delete(`${api}/projects/${project.id}`),
    ]);
  }
});

test("real Agent run publishes persisted USD usage and a settled turn to the installed widget", async ({
  page,
}, info) => {
  const project = await checked(
    await page.request.post(`${api}/projects`, { multipart: { title: "鲸鱼 Agent 用量" } }),
  );
  let providerId: string | undefined;
  let modelId: string | undefined;
  try {
    const card = await install(page);
    await card.getByRole("button", { name: "启用", exact: true }).click();
    const provider = await checked(
      await page.request.post(`${api}/model-providers`, {
        multipart: {
          name: "Whale E2E",
          provider_type: "openai_compatible",
          url: backend + "/_e2e/provider/v1",
          api_key: "dummy-model-key",
        },
      }),
    );
    providerId = provider.id;
    const model = await checked(
      await page.request.post(`${api}/models`, {
        data: {
          name: "Whale Model",
          model_id: "sdk-test-model",
          provider_id: providerId,
          context_length: 32000,
          input_price: 1,
          output_price: 2,
        },
      }),
    );
    modelId = model.id;
    await checked(
      await page.request.patch(`${api}/settings`, {
        data: { default_model: modelId, light_model: modelId, agent_bypass_tool_approval: true },
      }),
    );
    const session = await checked(
      await page.request.post(`${api}/agent/sessions`, {
        data: { project_id: project.id, model_id: modelId },
      }),
    );
    await checked(
      await page.request.post(`${api}/agent/sessions/${session.session_id}/message`, {
        data: { message: "请回复一句测试文本，不调用工具。" },
      }),
    );
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${api}/agent/sessions/${session.session_id}`)).json())
            .is_running,
        { timeout: 60000 },
      )
      .toBe(false);
    let task = await (await page.request.get(`${api}/tasks/${session.task_id}`)).json();
    expect(task.cost).toBeGreaterThan(0);
    await expect.poll(async () => (await storage(page)).lastTurn?.cost).toBeCloseTo(task.cost, 8);
    const record = await storage(page);
    expect(record.usage.length).toBeGreaterThan(0);
    expect(
      record.usage.every(
        (entry: { currency: string; revision: string }) =>
          entry.currency === "USD" && entry.revision,
      ),
    ).toBeTruthy();
    const previousCost = task.cost;
    const previousRevision = record.usage.at(-1).revision;
    await checked(
      await page.request.post(`${api}/agent/sessions/${session.session_id}/message`, {
        data: { message: "再回复一句测试文本，不调用工具。" },
      }),
    );
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${api}/agent/sessions/${session.session_id}`)).json())
            .is_running,
        { timeout: 60000 },
      )
      .toBe(false);
    task = await (await page.request.get(`${api}/tasks/${session.task_id}`)).json();
    await expect
      .poll(async () => (await storage(page)).lastTurn?.cost)
      .toBeCloseTo(task.cost - previousCost, 8);
    expect((await storage(page)).usage.at(-1).revision).not.toBe(previousRevision);
    await page.goto("/extensions/deepseek-whale/settings");
    const settings = page.locator('[data-plugin-view="deepseek-whale/settings"]');
    await expect(settings.locator("#model-cost")).toHaveText(`USD ${task.cost.toFixed(8)}`);
    await expect(page.locator("#whale-turn")).toContainText("上一轮 USD");
    await page.screenshot({
      path: info.outputPath("whale-agent-usage.png"),
      animations: "disabled",
    });
    expect(JSON.stringify(record)).not.toContain("dummy-model-key");
    expect(JSON.stringify(record)).not.toContain("whale-test-main");
  } finally {
    await page.request.patch(`${api}/settings`, {
      data: { default_model: null, light_model: null },
    });
    await page.request.delete(`${api}/plugins/deepseek-whale`);
    await page.request.delete(`${api}/projects/${project.id}`);
    if (modelId) await page.request.delete(`${api}/models/${modelId}`);
    if (providerId) await page.request.delete(`${api}/model-providers/${providerId}`);
  }
});
