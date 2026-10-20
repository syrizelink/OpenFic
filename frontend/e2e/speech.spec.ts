import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

let projectId: string;

function wave() {
  const buffer = Buffer.alloc(44 + 44100 * 2);
  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(buffer.length - 8, 4);
  buffer.write("WAVEfmt ", 8);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(44100, 24);
  buffer.writeUInt32LE(88200, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write("data", 36);
  buffer.writeUInt32LE(buffer.length - 44, 40);
  for (let i = 0; i < 44100; i++)
    buffer.writeInt16LE(Math.round(Math.sin((i / 44100) * 440 * 2 * Math.PI) * 5000), 44 + i * 2);
  return { name: "speech.wav", mimeType: "audio/wav", buffer };
}

async function configure(request: APIRequestContext, extra = {}) {
  const response = await request.put("/api/v1/audio/config", {
    data: {
      enabled: true,
      provider: "openai",
      api_key: "e2e-secret",
      config: { base_url: "http://127.0.0.1:18888/v1", model: "test-asr" },
      ...extra,
    },
  });
  expect(response.ok()).toBeTruthy();
}

async function openSpeech(page: Page) {
  await page.goto(`/projects/${projectId}`);
  const area = page.locator(".ai-sidebar-input-area");
  await expect(area).toBeVisible();
  await area.getByRole("button", { name: "选择音频文件", exact: true }).click();
  return page.getByRole("dialog", { name: "语音转写", exact: true });
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
  await page.keyboard.press("Escape");
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
    sensevoice: "本地 SenseVoice Small",
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

test("ASR settings use compact rows, save the toggle immediately and disclose optional paths", async ({
  page,
  request,
}, testInfo) => {
  await page.goto("/");
  await page.getByRole("button", { name: "设置", exact: true }).click();
  await page.getByRole("button", { name: "语音转写", exact: true }).click();
  const toggle = page.getByRole("switch", { name: "启用语音识别" });
  const saved = page.waitForResponse(
    (response) => response.url().endsWith("/audio/config") && response.request().method() === "PUT",
  );
  await toggle.click();
  expect((await (await saved).json()).enabled).toBe(false);
  const provider = page.getByRole("combobox", { name: "ASR 提供商" });
  await provider.click();
  await page.getByRole("option", { name: "本地 SenseVoice Small", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "SenseVoice 模型绝对路径（可选）" })).toBeHidden();
  await expect(provider.locator('[data-asr-provider="sensevoice"] svg')).toBeVisible();
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
  expect((await (await request.get("/api/v1/audio/config")).json()).enabled).toBe(false);
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
  for (const name of ["本地 SenseVoice Small", "OpenAI / OpenAI compatible"]) {
    await mobileProvider.click();
    await page.getByRole("button", { name, exact: true }).click();
    await expectProviderInline();
    expect(
      await page
        .locator(".audio-settings")
        .evaluate((node) => node.scrollWidth <= node.clientWidth + 1),
    ).toBe(true);
  }
});

test("microphone permission failure and empty transcripts are recoverable", async ({
  page,
  request,
}) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () =>
      Promise.reject(new DOMException("Permission denied", "NotAllowedError"));
  });
  await page.goto(`/projects/${projectId}`);
  await page
    .locator(".ai-sidebar-input-area")
    .getByRole("button", { name: "语音转写", exact: true })
    .click();
  await expect(page.locator(".agent-voice-input").getByRole("alert")).toContainText(
    "无法使用麦克风",
  );
  await page
    .locator(".agent-voice-input")
    .getByRole("button", { name: "取消", exact: true })
    .click();
  const dialog = await openSpeech(page);
  await request.post("http://127.0.0.1:18888/control", { data: { text: "" } });
  await dialog.getByLabel("选择音频文件").setInputFiles(wave());
  await expect(dialog.getByRole("alert")).toContainText("未识别到语音");
  await expect(dialog.getByRole("button", { name: "插入文字" })).toBeDisabled();
  await request.post("http://127.0.0.1:18888/control", { data: { text: "恢复成功" } });
  await dialog.getByRole("button", { name: "重试识别" }).click();
  await expect(dialog.getByRole("textbox", { name: "转写结果" })).toHaveValue("恢复成功");
});

test("upload is normalized, transcribed through Python and inserted into the composer", async ({
  page,
}) => {
  const dialog = await openSpeech(page);
  await dialog.getByLabel("选择音频文件").setInputFiles(wave());
  await expect(dialog.getByRole("textbox", { name: "转写结果" })).toHaveValue("语音转写测试。");
  await expect(page.locator(".ai-sidebar-input-body[data-mode='composer']")).not.toContainText(
    "语音转写测试。",
  );
  await dialog
    .getByRole("textbox", { name: "转写结果" })
    .fill("确认后的文字 <script>plain text</script>");
  await dialog.getByRole("button", { name: "插入文字" }).click();
  await expect(page.locator(".ai-sidebar-input-body[data-mode='composer']")).toContainText(
    "确认后的文字 <script>plain text</script>",
  );
});

test("inline microphone waveform narrows the composer and stop inserts without sending", async ({
  page,
  request,
}, testInfo) => {
  await page.goto(`/projects/${projectId}`);
  const area = page.locator(".ai-sidebar-input-area");
  const composer = page.locator(".ai-sidebar-input-body[data-mode='composer']");
  await expect(composer).toBeVisible();
  await composer.locator(".tiptap").fill("已有草稿");
  const normal = await area.boundingBox();
  let sends = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/agent/sessions")) sends++;
  });
  await area.getByRole("button", { name: "语音转写", exact: true }).click();
  const voice = page.locator(".agent-voice-input");
  const canvas = voice.getByRole("img", { name: "实时语音波形" });
  await expect(canvas).toBeVisible();
  await expect(composer).toBeHidden();
  expect((await area.boundingBox())!.width).toBeLessThan(normal!.width);
  await expect(voice.getByRole("button")).toHaveCount(2);
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

test("upstream error can be retried without losing the audio", async ({ page, request }) => {
  await request.post("http://127.0.0.1:18888/control", { data: { status: 500 } });
  const dialog = await openSpeech(page);
  await dialog.getByLabel("选择音频文件").setInputFiles(wave());
  await expect(dialog.getByRole("alert")).toContainText("HTTP 500");
  await request.post("http://127.0.0.1:18888/control", { data: { text: "重试成功" } });
  await dialog.getByRole("button", { name: "重试识别" }).click();
  await expect(dialog.getByRole("textbox", { name: "转写结果" })).toHaveValue("重试成功");
});

test("closing an active transcription cancels it and prevents stale results", async ({
  page,
  request,
}) => {
  await request.post("http://127.0.0.1:18888/control", {
    data: { delay: 10000, text: "过期结果" },
  });
  const dialog = await openSpeech(page);
  await dialog.getByLabel("选择音频文件").setInputFiles(wave());
  await expect
    .poll(async () => (await (await request.get("http://127.0.0.1:18888/control")).json()).calls)
    .toBe(1);
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await request.post("http://127.0.0.1:18888/control", { data: { text: "新结果" } });
  await page
    .locator(".ai-sidebar-input-area")
    .getByRole("button", { name: "选择音频文件", exact: true })
    .click();
  await expect(dialog.getByRole("textbox", { name: "转写结果" })).toBeEmpty();
  await dialog.getByLabel("选择音频文件").setInputFiles(wave());
  await expect(dialog.getByRole("textbox", { name: "转写结果" })).toHaveValue("新结果");
});

test("disabled ASR and malformed uploads display useful feedback", async ({ page, request }) => {
  await configure(request, { enabled: false });
  const dialog = await openSpeech(page);
  await expect(dialog.getByText("请先在设置 → 语音转写中启用并配置 ASR。")).toBeVisible();
  await expect(dialog.getByLabel("选择音频文件")).toBeDisabled();
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await configure(request);
  await page.reload();
  await page
    .locator(".ai-sidebar-input-area")
    .getByRole("button", { name: "选择音频文件", exact: true })
    .click();
  await dialog
    .getByLabel("选择音频文件")
    .setInputFiles({ name: "bad.wav", mimeType: "audio/wav", buffer: Buffer.from("bad audio") });
  await expect(dialog.getByRole("alert")).toBeVisible();
  const control = await request.get("http://127.0.0.1:18888/control");
  expect((await control.json()).calls).toBe(0);
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
  const dialog = await openSpeech(page);
  await dialog
    .getByLabel("选择音频文件")
    .setInputFiles({ name: "speech.wav", mimeType: "audio/wav", buffer: readFileSync(sample!) });
  await expect(dialog.getByRole("textbox", { name: "转写结果" })).toHaveValue(/tribal chieftain/i, {
    timeout: 60000,
  });
  await dialog.getByRole("button", { name: "插入文字" }).click();
  await expect(page.locator(".ai-sidebar-input-body[data-mode='composer']")).toContainText(
    /50 pieces of gold/i,
  );
});
