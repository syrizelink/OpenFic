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
  await area.getByRole("button", { name: "语音转写", exact: true }).click();
  return page.getByRole("dialog", { name: "语音转写", exact: true });
}

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
  for (const name of ["sensevoice", "whisper", "groq", "mistral", "deepgram", "azure", "openai"]) {
    await provider.selectOption(name);
    if (!["sensevoice", "whisper"].includes(name)) {
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

test("microphone permission failure and empty transcripts are recoverable", async ({
  page,
  request,
}) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () =>
      Promise.reject(new DOMException("Permission denied", "NotAllowedError"));
  });
  const dialog = await openSpeech(page);
  await dialog.getByRole("button", { name: "开始录音" }).click();
  await expect(dialog.getByRole("alert")).toContainText("无法使用麦克风");
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

test("browser microphone recording stops and transcribes", async ({ page }) => {
  const dialog = await openSpeech(page);
  await dialog.getByRole("button", { name: "开始录音" }).click();
  await expect(dialog.getByText("正在录音，最长 5 分钟…")).toBeVisible();
  await page.waitForTimeout(1500);
  await dialog.getByRole("button", { name: "停止并识别" }).click();
  await expect(dialog.getByRole("textbox", { name: "转写结果" })).toHaveValue("语音转写测试。");
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await expect(page.locator(".ai-sidebar-input-body[data-mode='composer']")).toBeEmpty();
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
    .getByRole("button", { name: "语音转写", exact: true })
    .click();
  await expect(dialog.getByRole("textbox", { name: "转写结果" })).toBeEmpty();
  await dialog.getByLabel("选择音频文件").setInputFiles(wave());
  await expect(dialog.getByRole("textbox", { name: "转写结果" })).toHaveValue("新结果");
});

test("disabled ASR and malformed uploads display useful feedback", async ({ page, request }) => {
  await configure(request, { enabled: false });
  const dialog = await openSpeech(page);
  await expect(dialog.getByText("请先在设置 → 语音转写中启用并配置 ASR。")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "开始录音" })).toBeDisabled();
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await configure(request);
  await page.reload();
  await page
    .locator(".ai-sidebar-input-area")
    .getByRole("button", { name: "语音转写", exact: true })
    .click();
  await dialog
    .getByLabel("选择音频文件")
    .setInputFiles({ name: "bad.wav", mimeType: "audio/wav", buffer: Buffer.from("bad audio") });
  await expect(dialog.getByRole("alert")).toBeVisible();
  const control = await request.get("http://127.0.0.1:18888/control");
  expect((await control.json()).calls).toBe(0);
});

test("chapter toolbar inserts plain text and persists it", async ({ page, request }) => {
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
  await toolbar.getByRole("button", { name: "语音转写", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "语音转写", exact: true });
  await dialog.getByLabel("选择音频文件").setInputFiles(wave());
  await expect(dialog.getByRole("textbox", { name: "转写结果" })).toHaveValue("语音转写测试。");
  await dialog.getByRole("textbox", { name: "转写结果" }).fill("<b>语音正文</b>");
  await dialog.getByRole("button", { name: "插入文字" }).click();
  await expect
    .poll(async () => (await (await request.get(`/api/v1/chapters/${chapterId}`)).json()).content)
    .toContain("<b>语音正文</b>");
  await expect(page.locator(".editor-toolbar").locator("..").locator(".tiptap")).toContainText(
    "<b>语音正文</b>",
  );
  await expect(page.locator(".editor-toolbar").locator("..").locator(".tiptap b")).toHaveCount(0);
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
