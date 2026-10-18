import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const backend = process.env.OPENFIC_E2E_BACKEND ?? "http://127.0.0.1:8011";
const api = `${backend}/api/v1`;
const root = fileURLToPath(new URL("../../", import.meta.url));
const fixtures = `${root}backend/tests/plugins/fixtures/claude-playground`;
const source = process.env.OPENFIC_OFFICIAL_MODS_DIR ?? fixtures;
const names = ["token-weather", "replay-theater", "blast-radius"];
test.use({ video: "off" });

test("unmodified official Mods: install, live token weather, native edit replay and explicit shell limitations", async ({
  page,
}, testInfo) => {
  await expect
    .poll(
      async () => {
        try {
          const response = await page.request.get(`${backend}/_e2e/drive`);
          return response.ok() && response.headers()["content-type"]?.includes("application/json");
        } catch {
          return false;
        }
      },
      { timeout: 30000 },
    )
    .toBeTruthy();
  if (process.env.OPENFIC_E2E_PASSWORD) {
    expect(
      (
        await page.request.post(`${api}/auth/login`, {
          data: { password: process.env.OPENFIC_E2E_PASSWORD },
        })
      ).ok(),
    ).toBeTruthy();
  }
  const provenance = JSON.parse(readFileSync(`${fixtures}/provenance.json`, "utf8"));
  for (const [path, checksum] of Object.entries(provenance.files)) {
    expect(
      createHash("sha256")
        .update(readFileSync(`${source}/${path}`))
        .digest("hex"),
    ).toBe(checksum);
  }
  for (const name of names) await page.request.delete(`${api}/plugins/${name}`);
  const projectResponse = await page.request.post(`${api}/projects`, {
    multipart: { title: "官方 Mods 端到端验证" },
  });
  expect(projectResponse.ok()).toBeTruthy();
  const project = await projectResponse.json();
  let modelId: string | undefined;
  let providerId: string | undefined;
  let agentSession: string | undefined;
  const previousSettings = await (await page.request.get(`${api}/settings`)).json();
  try {
    const volumes = await (await page.request.get(`${api}/projects/${project.id}/volumes`)).json();
    const chapterResponse = await page.request.post(`${api}/projects/${project.id}/chapters`, {
      data: {
        volume_id: volumes[0].id,
        title: "待编辑章节",
        content: "原来的句子\n保留的第二行",
        word_count: 12,
      },
    });
    expect(chapterResponse.ok()).toBeTruthy();
    const chapter = await chapterResponse.json();
    const provider = await page.request.post(`${api}/model-providers`, {
      multipart: {
        name: "Official Mods test provider",
        provider_type: "openai_compatible",
        url: `${backend}/_e2e/provider/v1`,
        api_key: "e2e-dummy-key",
      },
    });
    expect(provider.ok(), await provider.text()).toBeTruthy();
    providerId = (await provider.json()).id;
    const model = await page.request.post(`${api}/models`, {
      data: {
        name: "Official Mods model",
        model_id: "sdk-test-model",
        provider_id: providerId,
        context_length: 32000,
      },
    });
    expect(model.ok()).toBeTruthy();
    modelId = (await model.json()).id;
    expect(
      (
        await page.request.patch(`${api}/settings`, {
          data: { default_model: modelId, light_model: modelId, agent_bypass_tool_approval: true },
        })
      ).ok(),
    ).toBeTruthy();
    await page.goto("/extensions");
    await page.getByRole("checkbox").check();
    for (const name of names) {
      const zip = `/tmp/openfic-official-${name}.zip`;
      execFileSync("python3", [
        `${root}examples/plugins/build_package.py`,
        `${source}/${name}`,
        zip,
      ]);
      await page.locator('input[type="file"]').setInputFiles(zip);
      const card = page.locator(`[data-plugin-id="${name}"]`);
      await expect(card.getByText("0.1.0", { exact: true })).toBeVisible();
      await card.getByRole("button", { name: "启用", exact: true }).click();
      await expect(card.getByText("已启用", { exact: true })).toBeVisible();
    }
    const blastCard = page.locator('[data-plugin-id="blast-radius"]');
    await blastCard.getByText("Claude Mods compatibility", { exact: true }).click();
    await expect(blastCard).toContainText("Unsupported API: $.process");
    await expect(blastCard).toContainText("Unavailable tool: Bash");
    await page.screenshot({
      path: testInfo.outputPath("official-mods-manager.png"),
      fullPage: true,
    });
    // Exercise the original interaction in the conversation, without visiting a Mod page.
    await page.goto(`/projects/${project.id}`);
    await page.getByText("待编辑章节", { exact: true }).first().click();
    const weatherHost = page.locator(
      '[data-plugin-slot="assistant.above-prompt"] iframe[title="token-weather"]',
    );
    const replayHost = page.locator(
      '[data-plugin-slot="assistant.above-prompt"] iframe[title="replay-theater"]',
    );
    const weather = page.frameLocator(
      '[data-plugin-slot="assistant.above-prompt"] iframe[title="token-weather"]',
    );
    const replay = page.frameLocator(
      '[data-plugin-slot="assistant.above-prompt"] iframe[title="replay-theater"]',
    );
    const composer = page.locator('.agent-composer-prosemirror[contenteditable="true"]');
    await expect(composer).toBeVisible();
    await expect(weather.locator("#render")).toHaveAttribute("data-empty", "true");
    await expect.poll(async () => (await weatherHost.boundingBox())?.height ?? -1).toBe(0);
    await expect.poll(async () => (await replayHost.boundingBox())?.height ?? -1).toBe(0);
    await expect(
      page
        .getByRole("navigation", { name: "扩展", exact: true })
        .getByRole("link", { name: "token-weather", exact: true }),
    ).toHaveCount(0);
    const created = page.waitForResponse(
      (response) =>
        response.url() === `${api}/agent/sessions` && response.request().method() === "POST",
    );
    const sent = page.waitForResponse(
      (response) =>
        response.url().includes("/message") &&
        response.url().includes("/agent/sessions/") &&
        response.request().method() === "POST",
    );
    await composer.fill(
      `官方Mod兼容验证: ${JSON.stringify({ volumeTitle: volumes[0].title, chapterTitle: chapter.title })}`,
    );
    await page.getByRole("button", { name: "发送消息", exact: true }).click();
    const createdResponse = await created;
    expect(createdResponse.ok(), await createdResponse.text()).toBeTruthy();
    const session = await createdResponse.json();
    agentSession = session.session_id;
    expect((await sent).ok()).toBeTruthy();
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${api}/agent/sessions/${agentSession}`)).json())
            .is_running,
        { timeout: 60000 },
      )
      .toBe(false);
    const state = await (await page.request.get(`${api}/agent/sessions/${agentSession}`)).json();
    expect(state.error ?? null).toBeNull();
    const task = await (await page.request.get(`${api}/tasks/${session.task_id}`)).json();
    const calls = task.messages.flatMap(
      (message: { tool_calls?: { name: string }[] }) => message.tool_calls ?? [],
    );
    expect(calls.map((call: { name: string }) => call.name)).toEqual(
      expect.arrayContaining(["write_chapter", "edit_chapter"]),
    );
    expect(task.context_input_tokens).toBe(16000);
    expect(
      (await (await page.request.get(`${api}/chapters/${chapter.id}`)).json()).content,
    ).toContain("修改后的句子");
    const after = await (await page.request.get(`${api}/projects/${project.id}/chapters`)).json();
    expect(
      after.volumes
        .flatMap((volume: { chapters: { title: string }[] }) => volume.chapters)
        .some((item: { title: string }) => item.title === "官方Mod新章节"),
    ).toBeTruthy();
    await expect(page.locator(".ai-sidebar-messages")).toContainText("官方 Mod 验证完成");
    await expect(weather.locator("#render")).toContainText("50% of context");
    await expect(weather.locator("#render")).toContainText("16k / 32k");
    await expect(weather.locator("#render")).toContainText("Showers");
    await expect(weatherHost).toBeVisible();
    const weatherBox = (await weatherHost.boundingBox())!;
    const composerBox = (await composer.boundingBox())!;
    expect(weatherBox.height).toBeLessThanOrEqual(80);
    expect(weatherBox.y + weatherBox.height).toBeLessThanOrEqual(composerBox.y);
    expect(composerBox.y - weatherBox.y - weatherBox.height).toBeLessThan(100);
    expect(Math.abs(weatherBox.x - composerBox.x)).toBeLessThan(32);
    await page.screenshot({
      path: testInfo.outputPath("official-token-weather.png"),
      fullPage: true,
    });

    const conversationURL = page.url();
    await composer.fill("保留未发送的草稿");
    await expect(replay.getByRole("button", { name: "Replay", exact: true })).toBeVisible();
    await replay.getByRole("button", { name: "Replay", exact: true }).click();
    await expect(page).toHaveURL(conversationURL);
    await expect(replay.getByRole("region", { name: "Replay Theater", exact: true })).toBeVisible();
    await expect(replay.locator("#render")).toContainText("step 1 of 2");
    await expect(replay.locator("#render")).toContainText("+ 新建章节的第一行。");
    await expect
      .poll(async () => (await replayHost.boundingBox())?.height ?? 0)
      .toBeGreaterThan(100);
    expect((await replayHost.boundingBox())!.height).toBeLessThanOrEqual(420);
    expect((await page.locator(".ai-sidebar-messages").boundingBox())!.height).toBeGreaterThan(80);
    await expect(composer).toBeVisible();
    await expect(composer).toHaveText("保留未发送的草稿");
    await replay.getByRole("button", { name: "Next ▶", exact: true }).click();
    await expect(replay.locator("#render")).toContainText("step 2 of 2");
    await expect(replay.locator("#render")).toContainText("- 原来的句子");
    await expect(replay.locator("#render")).toContainText("+ 修改后的句子");
    await page.screenshot({
      path: testInfo.outputPath("official-replay-theater.png"),
      fullPage: true,
    });
    await replay.getByRole("button", { name: "◀ Prev", exact: true }).press("p");
    await expect(replay.locator("#render")).toContainText("step 1 of 2");
    await replay.getByRole("button", { name: "Close", exact: true }).click();
    await expect(replay.locator("#render")).toContainText("Replay: 2 edits");
    await expect(replay.getByRole("region", { name: "Replay Theater", exact: true })).toHaveCount(
      0,
    );
    await expect.poll(async () => (await replayHost.boundingBox())?.height ?? 100).toBeLessThan(80);
    await replay.getByRole("button", { name: "Replay", exact: true }).click();
    await expect(replay.locator("#render")).toContainText("step 1 of 2");
    await replay.getByRole("button", { name: "Close", exact: true }).press("Escape");
    await expect(replay.locator("#render")).toContainText("Replay: 2 edits");
    await expect(page).toHaveURL(conversationURL);
    await expect(composer).toHaveText("保留未发送的草稿");
    // The new general resize API may only resize its own iframe and is bounded.
    expect(
      await weather.locator("main").evaluate(async () => {
        const sdk = (
          window as unknown as { OpenFic: { ui: { resize(height: number): Promise<number> } } }
        ).OpenFic;
        return sdk.ui.resize(1e9);
      }),
    ).toBeLessThanOrEqual(420);
    await weather.locator("main").evaluate(async () => {
      const sdk = (
        window as unknown as { OpenFic: { ui: { resize(height: number): Promise<number> } } }
      ).OpenFic;
      return sdk.ui.resize(document.querySelector("main")!.getBoundingClientRect().height);
    });
    await page.goto(`/extensions/blast-radius/mod?projectId=${project.id}`);
    const blast = page.frameLocator('iframe[title="blast-radius"]');
    await expect(blast.locator("#status")).toContainText("Unsupported API: $.process");
    await expect(blast.locator("#status")).toContainText("Unavailable tool: Bash");
    const tools = await (await page.request.get(`${api}/agent/tools`)).json();
    expect(tools.some((tool: { name: string }) => tool.name === "Bash")).toBe(false);
    // Event contract check only: no shell command is executed.
    const blocked = await page.request.post(`${api}/plugins/blast-radius/rpc`, {
      data: {
        method: "sdk.hooks.preview",
        params: {
          event: "tool.call",
          data: { tool: "Bash", input: { command: "rm -rf nonexistent-compatibility-probe" } },
        },
      },
    });
    expect(blocked.ok(), await blocked.text()).toBeTruthy();
    expect((await blocked.json()).result.deny).toContain("Blast Radius");
    await page.screenshot({
      path: testInfo.outputPath("official-blast-radius-limitations.png"),
      fullPage: true,
    });
    await page.goto("/extensions");
    for (const name of names) {
      const card = page.locator(`[data-plugin-id="${name}"]`);
      await card.getByRole("button", { name: "停用", exact: true }).click();
      await expect(card.getByText("已停用", { exact: true })).toBeVisible();
      await card.getByRole("button", { name: "卸载", exact: true }).click();
      await page.getByRole("button", { name: "确认卸载", exact: true }).click();
      await expect(card).toHaveCount(0);
    }
  } finally {
    if (agentSession) await page.request.post(`${api}/agent/sessions/${agentSession}/cancel`);
    for (const name of names) await page.request.delete(`${api}/plugins/${name}`);
    await page.request.delete(`${api}/projects/${project.id}`);
    await page.request.patch(`${api}/settings`, {
      data: {
        default_model: previousSettings.default_model ?? "",
        light_model: previousSettings.light_model ?? "",
        agent_bypass_tool_approval: previousSettings.agent_bypass_tool_approval ?? false,
      },
    });
    if (modelId) await page.request.delete(`${api}/models/${modelId}`);
    if (providerId) await page.request.delete(`${api}/model-providers/${providerId}`);
  }
});
