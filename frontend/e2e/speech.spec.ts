import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

let projectId: string;

async function configure(request: APIRequestContext, extra = {}) {
  const response = await request.put("/api/v1/audio/config", {
    data: {
      provider: "openai",
      api_key: "e2e-secret",
      config: { base_url: "http://127.0.0.1:18888/v1", model: "test-asr" },
      ...extra,
    },
  });
  expect(response.ok()).toBeTruthy();
}

async function selectChatModel(request: APIRequestContext, page: Page) {
  const provider = await request.post("/api/v1/model-providers", {
    multipart: {
      name: "Voice E2E",
      provider_type: "openai",
      url: "http://127.0.0.1:18888/v1",
      api_key: "e2e-secret",
    },
  });
  expect(provider.status()).toBe(201);
  const model = await request.post("/api/v1/models", {
    data: {
      name: `Voice test model ${projectId}`,
      model_id: `voice-test-${projectId}`,
      provider_id: (await provider.json()).id,
    },
  });
  expect(model.status()).toBe(201);
  await page.addInitScript(
    (id) => localStorage.setItem("openfic.agent.selectedModelId", id),
    (await model.json()).id,
  );
}

async function startInline(page: Page) {
  await page
    .locator(".ai-sidebar-input-area")
    .getByRole("button", { name: "语音转写", exact: true })
    .click();
  const voice = page.locator(".agent-voice-input");
  await expect(voice.getByRole("img", { name: "实时语音波形" })).toBeVisible();
  await page.waitForTimeout(1000);
  return voice;
}

for (const draft of ["", "已有草稿"]) {
  test(`inline send ${draft ? "with draft" : "without draft"} bypasses the composer and submits once`, async ({
    page,
    request,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await selectChatModel(request, page);
    const messages: string[] = [];
    await page.route("**/api/v1/agent/sessions/*/message", (route) => {
      messages.push(route.request().postDataJSON().message);
      return route.fulfill({
        json: {
          success: true,
          session_id: route.request().url().split("/").at(-2),
          message: "sent",
        },
      });
    });
    await page.goto(`/projects/${projectId}`);
    const composer = page.locator(".ai-sidebar-input-body[data-mode='composer'] .tiptap");
    await expect(composer).toBeVisible();
    await composer.fill(draft);
    const normalSend = page.locator(".ai-sidebar-send-button");
    if (draft) await expect(normalSend).toBeEnabled();
    const normalSendBackground = await normalSend.evaluate(
      (node) => getComputedStyle(node).backgroundColor,
    );
    await composer.evaluate((node) => {
      const snapshots: string[] = [];
      (window as unknown as { speechDrafts: string[] }).speechDrafts = snapshots;
      new MutationObserver(() => snapshots.push(node.textContent ?? "")).observe(node, {
        childList: true,
        subtree: true,
        characterData: true,
      });
    });
    const voice = await startInline(page);
    const voiceSend = voice.getByRole("button", { name: "转写并发送" });
    await expect(voiceSend).toBeEnabled();
    if (draft) {
      expect(await voiceSend.evaluate((node) => getComputedStyle(node).backgroundColor)).toBe(
        normalSendBackground,
      );
    }
    await voice.getByRole("button", { name: "转写并发送" }).click();
    await expect
      .poll(() => messages)
      .toEqual([draft ? `${draft}\n语音转写测试。` : "语音转写测试。"]);
    await expect(voice).toHaveCount(0);
    await expect(composer).toBeEmpty();
    const drafts = await page.evaluate(
      () => (window as unknown as { speechDrafts: string[] }).speechDrafts,
    );
    expect(drafts.every((value) => !value.includes("语音转写测试。"))).toBe(true);
    expect(errors).toEqual([]);
  });
}

test("failed voice send retains the recording and can retry as text without sending", async ({
  page,
  request,
}) => {
  await selectChatModel(request, page);
  await request.post("http://127.0.0.1:18888/control", { data: { status: 500 } });
  let sends = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/agent/sessions")) sends++;
  });
  await page.goto(`/projects/${projectId}`);
  const composer = page.locator(".ai-sidebar-input-body[data-mode='composer'] .tiptap");
  await expect(composer).toBeVisible();
  await composer.fill("保留草稿");
  const voice = await startInline(page);
  await voice.getByRole("button", { name: "转写并发送" }).click();
  await expect(voice.getByRole("alert")).toContainText("HTTP 500");
  expect(sends).toBe(0);
  await expect(composer).toHaveText("保留草稿");
  await request.post("http://127.0.0.1:18888/control", { data: { text: "重试的文字" } });
  await voice.getByRole("button", { name: "停止并识别" }).click();
  await expect(composer).toBeVisible();
  await expect(composer).toContainText("重试的文字");
  expect(sends).toBe(0);
});

test("inline recording and pending transcription can be cancelled without changing the draft", async ({
  page,
  request,
}) => {
  await page.goto(`/projects/${projectId}`);
  const composer = page.locator(".ai-sidebar-input-body[data-mode='composer'] .tiptap");
  await expect(composer).toBeVisible();
  await composer.fill("原草稿");
  let voice = await startInline(page);
  await voice.getByRole("button", { name: "取消", exact: true }).click();
  await expect(voice).toHaveCount(0);
  await expect(composer).toHaveText("原草稿");
  expect((await (await request.get("http://127.0.0.1:18888/control")).json()).calls).toBe(0);
  await request.post("http://127.0.0.1:18888/control", { data: { delay: 10000, text: "旧结果" } });
  voice = await startInline(page);
  await voice.getByRole("button", { name: "停止并识别" }).click();
  await expect
    .poll(async () => (await (await request.get("http://127.0.0.1:18888/control")).json()).calls)
    .toBe(1);
  await voice.getByRole("button", { name: "取消", exact: true }).click();
  await expect(composer).toBeVisible();
  await expect(composer).toHaveText("原草稿");
});

test.beforeEach(async ({ request, page }) => {
  await request.put("/api/v1/settings", { data: { language: "zh-CN", telemetry_enabled: false } });
  await request.post("http://127.0.0.1:18888/control", { data: {} });
  await configure(request);
  const created = await request.post("/api/v1/projects", { multipart: { title: "ASR E2E" } });
  expect(created.status()).toBe(201);
  projectId = (await created.json()).id;
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "zh-CN"));
});

test.afterEach(async ({ request }) => {
  await request.delete(`/api/v1/projects/${projectId}`);
});

test("settings persist each provider and never return API keys", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "设置", exact: true }).click();
  await page.getByRole("button", { name: "语音转写", exact: true }).click();
  const provider = page.getByRole("combobox", { name: "ASR 提供商" });
  const providerLabels: Record<string, string> = {
    sensevoice: "Sense Voice (本地)",
    groq: "Groq",
    mistral: "Mistral",
    deepgram: "Deepgram",
    azure: "Azure Speech",
    openai: "OpenAI / OpenAI compatible",
  };
  for (const name of ["sensevoice", "groq", "mistral", "deepgram", "azure", "openai"]) {
    await provider.click();
    const option = page.getByRole("option", { name: providerLabels[name], exact: true });
    await expect(option.locator(`[data-asr-provider="${name}"] svg`)).toBeVisible();
    await option.click();
    await expect(provider.locator(`[data-asr-provider="${name}"] svg`)).toBeVisible();
    if (name !== "sensevoice") {
      await page.getByRole("textbox", { name: "ASR API Key" }).fill("e2e-secret");
    }
    const saved = page.waitForResponse(
      (response) =>
        response.url().endsWith("/audio/config") && response.request().method() === "PUT",
    );
    await page.getByRole("button", { name: "保存", exact: true }).click();
    const result = await saved;
    expect(result.status()).toBe(200);
    expect(await result.text()).not.toContain("e2e-secret");
    await expect(provider).toBeEnabled();
  }
  await page.reload();
  const config = await request.get("/api/v1/audio/config");
  expect((await config.json()).providers.azure.has_api_key).toBe(true);
  expect((await config.json()).providers.openai.base_url).toBe("http://127.0.0.1:18888/v1");
});

test("ASR settings use compact rows and disclose optional paths", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.getByRole("button", { name: "设置", exact: true }).click();
  await page.getByRole("button", { name: "语音转写", exact: true }).click();
  await expect(page.getByRole("switch")).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "模型下载源" })).toHaveCount(0);
  const provider = page.getByRole("combobox", { name: "ASR 提供商" });
  await provider.click();
  await page.getByRole("option", { name: "Sense Voice (本地)", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "SenseVoice 模型绝对路径（可选）" })).toBeHidden();
  await expect(provider.locator('[data-asr-provider="sensevoice"] svg')).toBeVisible();
  expect(
    await provider
      .locator(".select-option-label")
      .evaluate((node) => node.scrollWidth <= node.clientWidth),
  ).toBe(true);
  await page
    .getByRole("dialog")
    .screenshot({ path: testInfo.outputPath("asr-settings-local.png") });
  await page.getByText("自定义模型路径", { exact: true }).click();
  const modelPath = page.getByRole("textbox", { name: "SenseVoice 模型绝对路径（可选）" });
  await expect(modelPath).toBeVisible();
  await modelPath.fill("/opt/asr/model.int8.onnx");
  const persisted = page.waitForResponse(
    (response) => response.url().endsWith("/audio/config") && response.request().method() === "PUT",
  );
  await page.getByRole("button", { name: "保存", exact: true }).click();
  expect((await (await persisted).json()).providers.sensevoice.model_path).toBe(
    "/opt/asr/model.int8.onnx",
  );
  expect((await provider.boundingBox())!.width).toBe(192);
  expect((await modelPath.locator("..").boundingBox())!.width).toBe(192);
  await provider.click();
  await page.getByRole("option", { name: "Groq", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "ASR API Key" })).toBeVisible();
  await page
    .getByRole("dialog")
    .screenshot({ path: testInfo.outputPath("asr-settings-cloud.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "语音转写", exact: true }).click();
  const mobileProvider = page.getByRole("button", { name: "ASR 提供商", exact: true });
  await mobileProvider.click();
  const groq = page.getByRole("button", { name: "Groq", exact: true });
  await expect(groq.locator('[data-asr-provider="groq"] svg')).toBeVisible();
  await groq.click();
  await expect(page.getByRole("textbox", { name: "ASR API Key" })).toBeVisible();
  expect(
    await page
      .locator(".audio-settings")
      .evaluate((node) => node.scrollWidth <= node.clientWidth + 1),
  ).toBe(true);
  await expect(page.locator("[data-sonner-toast]")).toHaveCount(0);
  const expectProviderInline = async () => {
    const aligned = await mobileProvider.evaluate((trigger) => {
      const label = trigger.closest(".audio-settings-row")?.querySelector(".audio-settings-label");
      if (!label) return false;
      const labelRect = label.getBoundingClientRect();
      const triggerRect = trigger.getBoundingClientRect();
      return (
        Math.abs(labelRect.top + labelRect.height / 2 - triggerRect.top - triggerRect.height / 2) <
          2 && triggerRect.left >= labelRect.right
      );
    });
    expect(aligned).toBe(true);
  };
  await expectProviderInline();
  await page.screenshot({ path: testInfo.outputPath("asr-settings-mobile.png") });
  await page.setViewportSize({ width: 320, height: 844 });
  for (const name of ["Sense Voice (本地)", "OpenAI / OpenAI compatible"]) {
    await mobileProvider.click();
    await page.getByRole("button", { name, exact: true }).click();
    await expectProviderInline();
    if (name === "Sense Voice (本地)") {
      expect(
        await mobileProvider
          .locator(".select-option-label")
          .evaluate((node) => node.scrollWidth <= node.clientWidth),
      ).toBe(true);
    }
    expect(
      await page
        .locator(".audio-settings")
        .evaluate((node) => node.scrollWidth <= node.clientWidth + 1),
    ).toBe(true);
  }
});

test("microphone permission failure is recoverable through cancel", async ({ page }) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () =>
      Promise.reject(new DOMException("Permission denied", "NotAllowedError"));
  });
  await page.goto(`/projects/${projectId}`);
  const composer = page.locator(".ai-sidebar-input-body[data-mode='composer'] .tiptap");
  await composer.fill("权限失败前的草稿");
  await page.getByRole("button", { name: "语音转写", exact: true }).click();
  const voice = page.locator(".agent-voice-input");
  await expect(voice.getByRole("alert")).toContainText("无法使用麦克风");
  await expect(voice.getByRole("button", { name: "停止并识别" })).toBeDisabled();
  await voice.getByRole("button", { name: "取消", exact: true }).click();
  await expect(composer).toBeVisible();
  await expect(composer).toHaveText("权限失败前的草稿");
  await expect(composer).not.toBeFocused();
});

test("empty transcripts retain the recording and can retry without losing the draft", async ({
  page,
  request,
}) => {
  await request.post("http://127.0.0.1:18888/control", { data: { text: "" } });
  await page.goto(`/projects/${projectId}`);
  const composer = page.locator(".ai-sidebar-input-body[data-mode='composer'] .tiptap");
  await composer.fill("原草稿");
  const voice = await startInline(page);
  await voice.getByRole("button", { name: "停止并识别" }).click();
  await expect(voice.getByRole("alert")).toContainText("未识别到语音");
  await request.post("http://127.0.0.1:18888/control", { data: { text: "恢复成功" } });
  await voice.getByRole("button", { name: "停止并识别" }).click();
  await expect(composer).toBeVisible();
  await expect(composer).toContainText("原草稿");
  await expect(composer).toContainText("恢复成功");
});

test("inline microphone reuses the composer styling, moves down and stops without sending", async ({
  page,
  request,
}, testInfo) => {
  await page.goto(`/projects/${projectId}`);
  const area = page.locator(".ai-sidebar-input-area");
  const composer = page.locator(".ai-sidebar-input-body[data-mode='composer']");
  await expect(composer).toBeVisible();
  const unfocusedBorder = await page
    .locator(".ai-sidebar-input-container")
    .evaluate((node) => getComputedStyle(node).borderColor);
  await composer.locator(".tiptap").fill("已有草稿");
  const container = page.locator(".ai-sidebar-input-container");
  const normal = (await container.boundingBox())!;
  const radius = await container.evaluate((node) => getComputedStyle(node).borderRadius);
  const sendSize = (await area.locator(".ai-sidebar-send-button").boundingBox())!;
  await area.screenshot({ path: testInfo.outputPath("voice-before.png") });
  let sends = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/agent/sessions")) sends++;
  });
  await area.getByRole("button", { name: "语音转写", exact: true }).click();
  const voice = page.locator(".agent-voice-input");
  const canvas = voice.getByRole("img", { name: "实时语音波形" });
  await expect(canvas).toBeVisible();
  await expect(voice).not.toBeFocused();
  await voice.getByRole("button", { name: "取消", exact: true }).focus();
  await expect
    .poll(() => container.evaluate((node) => getComputedStyle(node).borderColor))
    .toBe(unfocusedBorder);
  await expect(composer).toBeHidden();
  await expect.poll(async () => Math.round((await container.boundingBox())!.height)).toBe(44);
  const recording = (await container.boundingBox())!;
  expect(recording.y).toBeGreaterThan(normal.y);
  expect(recording.height).toBeLessThan(normal.height);
  expect(recording.width).toBeCloseTo(normal.width, 0);
  expect(await container.evaluate((node) => getComputedStyle(node).borderRadius)).toBe(radius);
  await expect(area.locator(".ai-sidebar-input-toolbar")).toBeHidden();
  await expect(voice.getByRole("button")).toHaveCount(3);
  const cancel = (await voice.getByRole("button", { name: "取消", exact: true }).boundingBox())!;
  const wave = (await canvas.boundingBox())!;
  expect(cancel.x).toBeLessThan(wave.x);
  for (const button of await voice.getByRole("button").all()) {
    const box = (await button.boundingBox())!;
    expect(box.width).toBe(sendSize.width);
    expect(box.height).toBe(sendSize.height);
  }
  const first = await canvas.evaluate((node) => (node as HTMLCanvasElement).toDataURL());
  await expect
    .poll(() => canvas.evaluate((node) => (node as HTMLCanvasElement).toDataURL()))
    .not.toBe(first);
  await page.waitForTimeout(1000);
  await area.screenshot({ path: testInfo.outputPath("voice-recording.png") });
  await voice.getByRole("button", { name: "停止并识别" }).click();
  await expect(composer).toBeVisible();
  await expect(composer).toContainText("已有草稿");
  await expect(composer).toContainText("语音转写测试。");
  expect(sends).toBe(0);
  expect((await (await request.get("http://127.0.0.1:18888/control")).json()).calls).toBe(1);
});

test("recording is available without a feature switch and reports unprepared local models", async ({
  page,
  request,
}) => {
  await configure(request, { provider: "sensevoice", config: {} });
  await page.goto(`/projects/${projectId}`);
  const voice = await startInline(page);
  await voice.getByRole("button", { name: "停止并识别" }).click();
  await expect(voice.getByRole("alert")).toContainText("Prepare the SenseVoice model");
  await voice.getByRole("button", { name: "取消", exact: true }).click();
  await expect(page.locator(".ai-sidebar-input-toolbar")).toBeVisible();
  expect((await (await request.get("http://127.0.0.1:18888/control")).json()).calls).toBe(0);
});

test("chapter toolbar has no transcription entry while Agent voice input remains available", async ({
  page,
  request,
}) => {
  const volume = await request.post(`/api/v1/projects/${projectId}/volumes`, {
    data: { title: "测试卷" },
  });
  const chapter = await request.post(`/api/v1/projects/${projectId}/chapters`, {
    data: { volume_id: (await volume.json()).id, title: "语音测试章节", content: "原有正文" },
  });
  const chapterId = (await chapter.json()).id;
  await page.goto(`/projects/${projectId}`);
  await page.getByText("语音测试章节", { exact: true }).first().click();
  const toolbar = page.locator(".editor-toolbar");
  await expect(toolbar).toBeVisible();
  await expect(toolbar.getByRole("button", { name: "语音转写", exact: true })).toHaveCount(0);
  await expect(toolbar.getByRole("button", { name: "选择音频文件", exact: true })).toHaveCount(0);
  await expect(
    page.locator(".ai-sidebar-input-area").getByRole("button", { name: "语音转写", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .locator(".ai-sidebar-input-area")
      .getByRole("button", { name: "选择音频文件", exact: true }),
  ).toHaveCount(0);
  const saved = await request.get(`/api/v1/chapters/${chapterId}`);
  expect((await saved.json()).content).toBe("原有正文");
});

test("real SenseVoice model transcribes a speech recording through the UI", async ({
  page,
  request,
}) => {
  const modelDir = process.env.OPENFIC_ASR_MODEL_DIR;
  const sample = process.env.OPENFIC_ASR_SAMPLE;
  test.skip(
    !modelDir || !sample,
    "Set model directory and a sample WAV to run native ASR verification",
  );
  await configure(request, {
    provider: "sensevoice",
    language: "en",
    config: {
      model_path: join(modelDir!, "model.int8.onnx"),
      tokens_path: join(modelDir!, "tokens.txt"),
      vad_path: join(modelDir!, "silero_vad.onnx"),
    },
  });
  await page.goto(`/projects/${projectId}`);
  const voice = await startInline(page);
  // The ASR Playwright config feeds OPENFIC_ASR_SAMPLE into the fake microphone.
  await page.waitForTimeout(Math.min(60000, readFileSync(sample!).length / 32 + 1000));
  await voice.getByRole("button", { name: "停止并识别" }).click();
  const composer = page.locator(".ai-sidebar-input-body[data-mode='composer']");
  await expect(composer).toContainText(/tribal chieftain/i, { timeout: 60000 });
  await expect(composer).toContainText(/50 pieces of gold/i);
});

// UI contract coverage uses controlled transfer snapshots; Python tests exercise
// source probing, streaming, checksum validation, fallback and progress endpoints.
test("model preparation shows live progress and replaces controls with a ready badge", async ({
  page,
  request,
}, testInfo) => {
  await configure(request, { provider: "sensevoice", config: {} });
  let progress = { status: "idle", downloaded_bytes: 0, total_bytes: 0, file_name: "", source: "" };
  let release!: () => void;
  const transfer = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/audio/prepare/status", (route) => route.fulfill({ json: progress }));
  await page.route("**/audio/local-status", (route) =>
    route.fulfill({
      json: { sensevoice_ready: progress.status === "ready" },
    }),
  );
  await page.route("**/audio/prepare", async (route) => {
    progress = {
      status: "downloading",
      downloaded_bytes: 60_000_000,
      total_bytes: 240_000_000,
      file_name: "model.int8.onnx",
      source: "hf-mirror.com",
    };
    await transfer;
    await route.fulfill({ json: { ready: true } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "设置", exact: true }).click();
  await page.getByRole("button", { name: "语音转写", exact: true }).click();
  const provider = page.getByRole("combobox", { name: "ASR 提供商", exact: true });
  await page.getByRole("button", { name: "准备模型", exact: true }).click();
  try {
    const bar = page.getByRole("progressbar", { name: "模型下载进度" });
    await expect(bar).toHaveAttribute("aria-valuenow", "25");
    await expect(
      page.getByText("model.int8.onnx · hf-mirror.com · 60.0 / 240.0 MB", { exact: true }),
    ).toBeVisible();
    await expect(provider).toBeDisabled();
    await page
      .getByRole("dialog")
      .screenshot({ path: testInfo.outputPath("asr-download-desktop.png") });
    progress = { ...progress, downloaded_bytes: 168_000_000 };
    await expect(bar).toHaveAttribute("aria-valuenow", "70");
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("button", { name: "语音转写", exact: true }).click();
    await expect(bar).toHaveAttribute("aria-valuenow", "70");
    await expect(page.locator("[data-sonner-toast]")).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath("asr-download-mobile.png") });
    expect(
      await page
        .locator(".audio-settings")
        .evaluate((node) => node.scrollWidth <= node.clientWidth + 1),
    ).toBe(true);
    progress = { ...progress, status: "verifying", downloaded_bytes: 240_000_000 };
    await expect(bar).toHaveAttribute("aria-valuenow", "99");
    await expect(page.getByText("正在校验模型…", { exact: true })).toBeVisible();
    progress = { ...progress, status: "ready", file_name: "", source: "" };
    release();
    await expect(page.getByRole("button", { name: "准备模型", exact: true })).toHaveCount(0);
    await expect(page.getByText("已就绪", { exact: true })).toBeVisible();
    await expect(bar).toHaveCount(0);
    await page.setViewportSize({ width: 1600, height: 1000 });
    await page.goto("/");
    await page.getByRole("button", { name: "设置", exact: true }).click();
    await page.getByRole("button", { name: "语音转写", exact: true }).click();
    await expect(page.getByText("已就绪", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "准备模型", exact: true })).toHaveCount(0);
    await expect(bar).toHaveCount(0);
    await expect(page.getByText("SenseVoice Small · INT8", { exact: true })).toBeVisible();
    expect(
      await page
        .getByText("已就绪", { exact: true })
        .evaluate((node) => getComputedStyle(node).fontWeight),
    ).toBe("700");
    await page
      .getByRole("dialog")
      .screenshot({ path: testInfo.outputPath("asr-settings-ready.png") });
  } finally {
    release();
  }
});

test("failed model preparation keeps progress and allows retry", async ({ page, request }) => {
  await configure(request, { provider: "sensevoice", config: {} });
  let failed = false;
  await page.route("**/audio/prepare/status", (route) =>
    route.fulfill({
      json: {
        status: failed ? "failed" : "idle",
        downloaded_bytes: failed ? 24_000_000 : 0,
        total_bytes: failed ? 240_000_000 : 0,
        file_name: "model.int8.onnx",
        source: "huggingface.co",
      },
    }),
  );
  await page.route("**/audio/prepare", async (route) => {
    failed = true;
    await route.fulfill({ status: 502, json: { detail: "Download failed" } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "设置", exact: true }).click();
  await page.getByRole("button", { name: "语音转写", exact: true }).click();
  const prepare = page.getByRole("button", { name: "准备模型", exact: true });
  await prepare.click();
  await expect(page.getByText("下载失败，可重试", { exact: true })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "模型下载进度" })).toHaveAttribute(
    "aria-valuenow",
    "10",
  );
  await expect(prepare).toBeEnabled();
  await prepare.click();
  await expect(prepare).toBeEnabled();
});

for (const [width, reducedMotion] of [
  [390, "no-preference"],
  [320, "reduce"],
] as const) {
  test(`voice layout fits ${width}px and restores the toolbar after cancel (${reducedMotion})`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 844 });
    await page.emulateMedia({ reducedMotion });
    await page.goto(`/projects/${projectId}`);
    const area = page.locator(".ai-sidebar-input-area");
    if (!(await area.isVisible()))
      await page.getByRole("button", { name: "Agent", exact: true }).click();
    await expect(area).toBeVisible();
    const composer = area.locator(".tiptap");
    await composer.fill("手机草稿");
    const container = area.locator(".ai-sidebar-input-container");
    const normal = (await container.boundingBox())!;
    const trigger = area.getByRole("button", { name: "语音转写", exact: true });
    await trigger.hover();
    const triggerStyle = await trigger.evaluate((node) => {
      const style = getComputedStyle(node);
      return {
        width: style.width,
        height: style.height,
        radius: style.borderRadius,
        background: style.backgroundColor,
      };
    });
    expect(triggerStyle.width).toBe("26px");
    expect(triggerStyle.height).toBe("26px");
    expect(triggerStyle.radius).toBe("50%");
    await trigger.click();
    const voice = area.locator(".agent-voice-input");
    await expect(voice.getByRole("img", { name: "实时语音波形" })).toBeVisible();
    await expect.poll(async () => Math.round((await container.boundingBox())!.height)).toBe(44);
    expect((await container.boundingBox())!.y).toBeGreaterThan(normal.y);
    expect((await container.boundingBox())!.width).toBeCloseTo(normal.width, 0);
    await expect(area.locator(".ai-sidebar-input-toolbar")).toBeHidden();
    expect(await area.evaluate((node) => node.scrollWidth <= node.clientWidth + 1)).toBe(true);
    await expect(area.getByRole("button", { name: "选择音频文件", exact: true })).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath(`voice-mobile-${width}.png`) });
    if (reducedMotion === "reduce") await page.keyboard.press("Escape");
    else await voice.getByRole("button", { name: "取消", exact: true }).click();
    await expect(voice).toHaveCount(0);
    await expect(area.locator(".ai-sidebar-input-toolbar")).toBeVisible();
    await expect(composer).toHaveText("手机草稿");
    await expect(composer).not.toBeFocused();
    await expect
      .poll(async () => Math.round((await container.boundingBox())!.height))
      .toBe(Math.round(normal.height));
  });
}

test("ASR settings show loading and fetch fresh data on every category entry", async ({
  page,
  request,
}) => {
  let requests = 0;
  const release: Array<() => void> = [];
  await page.route("**/audio/config", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    requests++;
    await new Promise<void>((resolve) => {
      release.push(resolve);
    });
    await route.continue();
  });
  await page.goto("/");
  await page.getByRole("button", { name: "设置", exact: true }).click();
  for (let entry = 0; entry < 2; entry++) {
    if (entry) {
      await page.getByRole("button", { name: "联网搜索", exact: true }).click();
      await configure(request, { language: "ja" });
    }
    await page.getByRole("button", { name: "语音转写", exact: true }).click();
    try {
      await expect.poll(() => requests).toBe(entry + 1);
      await expect(page.locator(".audio-settings-loading")).toBeVisible();
      await expect(page.getByRole("combobox", { name: "ASR 提供商" })).toHaveCount(0);
    } finally {
      release[entry]?.();
    }
    await expect(page.getByRole("combobox", { name: "ASR 提供商" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "识别语言", exact: true })).toHaveValue(
      entry ? "ja" : "auto",
    );
    if (!entry) await page.getByRole("textbox", { name: "识别语言", exact: true }).fill("zh");
  }
});
