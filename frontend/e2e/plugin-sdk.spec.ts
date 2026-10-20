import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const backend = process.env.OPENFIC_E2E_BACKEND ?? "http://127.0.0.1:8011";
const api = `${backend}/api/v1`;
const root = fileURLToPath(new URL("../../", import.meta.url));
const examples = ["google-drive-sync", "handoff-workflow", "prompt-elements"];
test.use({ video: "off" });
test.beforeEach(async ({ page }) => {
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
});

async function openPlugin(page: Page, id: string, view: string, projectId: string) {
  await page.goto(`/extensions/${id}/${view}?projectId=${projectId}`);
  const native = page.locator(`[data-plugin-view="${id}/${view}"]`);
  await expect(native.locator(".example-page")).toBeVisible();
  await expect(native.locator("iframe")).toHaveCount(0);
  return native;
}

test("SDK examples: Drive OAuth/conflicts/Agent tool, handoff graph, prompt injection and editor", async ({
  page,
}) => {
  if (process.env.OPENFIC_E2E_PASSWORD) {
    expect(
      (
        await page.request.post(`${api}/auth/login`, {
          data: { password: process.env.OPENFIC_E2E_PASSWORD },
        })
      ).ok(),
    ).toBeTruthy();
  }
  // This test requires the dedicated tests.plugins.e2e_app; never point at user data.
  expect((await page.request.get(`${backend}/_e2e/drive`)).ok()).toBeTruthy();
  const created = await page.request.post(`${api}/projects`, {
    multipart: { title: "SDK 示例端到端验证" },
  });
  expect(created.status()).toBe(201);
  const project = await created.json();
  let providerId: string | undefined;
  let modelId: string | undefined;
  try {
    const volumes = await (await page.request.get(`${api}/projects/${project.id}/volumes`)).json();
    const chapter = await (
      await page.request.post(`${api}/projects/${project.id}/chapters`, {
        data: {
          title: "验证章节",
          volume_id: volumes[0].id,
          content: "初始章节内容。",
          word_count: 7,
        },
      })
    ).json();
    const provider = await page.request.post(`${api}/model-providers`, {
      multipart: {
        name: "SDK test provider",
        provider_type: "openai_compatible",
        url: `${backend}/_e2e/provider/v1`,
        api_key: "e2e-dummy-key",
      },
    });
    expect(provider.ok(), await provider.text()).toBeTruthy();
    providerId = (await provider.json()).id;
    const model = await page.request.post(`${api}/models`, {
      data: {
        name: "SDK Test Model",
        model_id: "sdk-test-model",
        provider_id: providerId,
        context_length: 32000,
      },
    });
    expect(model.ok(), await model.text()).toBeTruthy();
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
    for (const id of examples) {
      const { version } = JSON.parse(
        readFileSync(`${root}examples/plugins/${id}/plugin.json`, "utf8"),
      );
      execFileSync("python3", [
        `${root}examples/plugins/build_package.py`,
        `${root}examples/plugins/${id}`,
        `${root}examples/plugins/dist/${id}-${version}.zip`,
      ]);
      await page
        .locator('input[type="file"]')
        .setInputFiles(`${root}examples/plugins/dist/${id}-${version}.zip`);
      const card = page.locator(`[data-plugin-id="${id}"]`);
      await expect(card).toBeVisible();
      await card.getByRole("button", { name: "启用", exact: true }).click();
      await expect(card.getByText("已启用", { exact: true })).toBeVisible();
    }
    await page.request.put(`${api}/plugins/google-drive-sync/settings`, {
      data: { settings: { clientId: "test-client", clientSecret: "test-secret", folderId: "" } },
    });
    const drive = await openPlugin(page, "google-drive-sync", "sync", project.id);
    await expect(drive.locator("#connection")).toHaveText("尚未连接");
    await drive.getByRole("button", { name: "连接 Google Drive", exact: true }).click();
    const authorize = drive.getByRole("link", { name: "打开 Google 授权页面", exact: true });
    await expect(authorize).toBeVisible();
    const authorizationURL = await authorize.getAttribute("href");
    const state = new URL(authorizationURL!).searchParams.get("state");
    expect(
      (
        await page.request.get(
          `${backend}/plugin-oauth/callback?state=${state}&code=test-auth-code`,
        )
      ).ok(),
    ).toBeTruthy();
    expect(
      (
        await page.request.get(
          `${backend}/plugin-oauth/callback?state=${state}&code=test-auth-code`,
        )
      ).status(),
    ).toBe(400);
    await expect(drive.locator("#connection")).toHaveText("已连接");
    await drive.getByRole("button", { name: "立即同步", exact: true }).click();
    await expect(drive.locator("#status")).toHaveText("同步完成");
    await expect(drive.locator("#report")).toContainText("上传 1");
    let remote = (await (await page.request.get(`${backend}/_e2e/drive`)).json()).files.find(
      (f: { payload: { chapterId: string } }) => f.payload.chapterId === chapter.id,
    );
    expect(remote.payload.content).toBe("初始章节内容。");
    await page.request.patch(`${api}/chapters/${chapter.id}`, { data: { content: "本地编辑。" } });
    await page.request.post(`${backend}/_e2e/drive/change`, {
      data: { id: remote.id, content: "云端编辑。" },
    });
    await drive.getByRole("button", { name: "立即同步", exact: true }).click();
    await expect(drive.locator("#conflicts")).toContainText("本地与云端均有修改");
    await drive.getByRole("button", { name: "使用云端版本" }).click();
    const confirmation = page.getByRole("alertdialog");
    await expect(confirmation).toBeVisible();
    await page.screenshot({
      path: test.info().outputPath("drive-conflict-dialog.png"),
      animations: "disabled",
    });
    await confirmation.getByRole("button", { name: "确认覆盖" }).click();
    await expect(drive.locator("#report")).toContainText("下载 1");
    expect((await (await page.request.get(`${api}/chapters/${chapter.id}`)).json()).content).toBe(
      "云端编辑。",
    );

    const handoff = await openPlugin(page, "handoff-workflow", "workflow", project.id);
    await handoff.locator('[data-plugin-component="ModelIdSelect"]').getByRole("button").click();
    await page.getByText("SDK Test Model", { exact: true }).click();
    await handoff.getByRole("button", { name: "运行工作流", exact: true }).click();
    await expect(handoff.locator("#status")).toHaveText("工作流完成", { timeout: 60000 });
    await expect(handoff.locator("#trace")).toContainText("planner → writer");
    await expect(handoff.locator("#trace")).toContainText("writer → reviewer");
    await expect(handoff.locator("#output")).toContainText("真实模型路径审核通过");
    await handoff.getByRole("button", { name: "保存为项目笔记" }).click();
    await expect(handoff.locator("#status")).toHaveText("已保存为项目笔记");
    await handoff.getByRole("button", { name: "为此项目启用 Handoff" }).click();
    await expect(handoff.locator("#status")).toContainText("已为此项目启用");
    const handoffRequestStart = (
      await (await page.request.get(`${backend}/_e2e/model-requests`)).json()
    ).length;
    const session = await page.request.post(`${api}/agent/sessions`, {
      data: { project_id: project.id, model_id: modelId },
    });
    expect(session.ok(), await session.text()).toBeTruthy();
    const sessionData = await session.json();
    expect(
      (
        await page.request.post(`${api}/agent/sessions/${sessionData.session_id}/message`, {
          data: { message: "用 handoff 写一个重逢故事。" },
        })
      ).ok(),
    ).toBeTruthy();
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${api}/agent/sessions/${sessionData.session_id}`)).json())
            .is_running,
        { timeout: 60000 },
      )
      .toBe(false);
    const recorded = await (await page.request.get(`${backend}/_e2e/model-requests`)).json();
    expect(
      recorded
        .slice(handoffRequestStart)
        .some((r: { messages: { content: unknown }[] }) =>
          r.messages.some((m) => String(m.content).includes("reviewer in a handoff")),
        ),
    ).toBeTruthy();
    const task = await (await page.request.get(`${api}/tasks/${sessionData.task_id}`)).json();
    expect(
      task.messages.some(
        (m: { role: string; content: string }) =>
          m.role === "assistant" && m.content.includes("真实模型路径审核通过"),
      ),
    ).toBeTruthy();
    const handoffCalls = task.messages.flatMap(
      (m: { tool_calls?: { id: string }[] }) => m.tool_calls ?? [],
    );
    for (const call of handoffCalls)
      expect(
        task.messages.some(
          (m: { role: string; tool_call_id?: string }) =>
            m.role === "tool" && m.tool_call_id === call.id,
        ),
      ).toBeTruthy();
    await handoff.getByRole("button", { name: "恢复内置工作流" }).click();
    await expect(handoff.locator("#status")).toHaveText("已恢复内置工作流");

    const prompt = await openPlugin(page, "prompt-elements", "rules", project.id);
    await prompt.getByRole("button", { name: "预览注入结果" }).click();
    await expect(prompt.locator("#matched")).toContainText("combat-detection");
    await expect(prompt.locator("#output")).toContainText("不可靠感知");
    await prompt.getByRole("button", { name: "保存规则", exact: true }).click();
    await expect(prompt.locator("#status")).toContainText("规则已保存");
    const driveRequestStart = (await (await page.request.get(`${backend}/_e2e/drive`)).json())
      .requests.length;
    const nativeRequestStart = (
      await (await page.request.get(`${backend}/_e2e/model-requests`)).json()
    ).length;
    const native = await page.request.post(`${api}/agent/sessions`, {
      data: { project_id: project.id, model_id: modelId },
    });
    expect(native.ok(), await native.text()).toBeTruthy();
    const nativeData = await native.json();
    await page.request.post(`${api}/agent/sessions/${nativeData.session_id}/message`, {
      data: { message: "插件同步验证：请手动触发云同步，然后描写梦境中的战斗。" },
    });
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${api}/agent/sessions/${nativeData.session_id}`)).json())
            .is_running,
        { timeout: 60000 },
      )
      .toBe(false);
    const stateAfter = await (
      await page.request.get(`${api}/agent/sessions/${nativeData.session_id}`)
    ).json();
    expect(stateAfter.error ?? null).toBeNull();
    const calls = await (await page.request.get(`${backend}/_e2e/model-requests`)).json();
    expect(
      calls
        .slice(nativeRequestStart)
        .some((r: { messages: { content: unknown }[] }) =>
          r.messages.some((m) => String(m.content).includes("空间位置")),
        ),
    ).toBeTruthy();
    expect(
      (await (await page.request.get(`${backend}/_e2e/drive`)).json()).requests.length,
    ).toBeGreaterThan(driveRequestStart);
    remote = (await (await page.request.get(`${backend}/_e2e/drive`)).json()).files.find(
      (f: { payload: { chapterId: string } }) => f.payload.chapterId === chapter.id,
    );
    expect(remote).toBeTruthy();
    const logs = await (await page.request.get(`${api}/plugins/google-drive-sync/logs`)).json();
    expect(logs).toBeTruthy();

    await page.goto(`/projects/${project.id}`);
    await page.getByText("验证章节", { exact: true }).first().click();
    await expect(page.locator(".tiptap.ProseMirror").first()).toBeVisible();
    await page
      .locator('.editor-toolbar [data-plugin-slot="editor.toolbar"]')
      .getByRole("button", { name: "提示词与编辑器", exact: true })
      .click();
    const editor = page.locator('[data-plugin-view="prompt-elements/editor"]');
    await editor.getByRole("button", { name: "读取编辑器" }).click();
    await expect(editor.locator("#status")).toContainText("验证章节");
    await editor.getByLabel("插入文本").fill("插件写入并保存。");
    await editor.getByRole("button", { name: "插入并保存" }).click();
    await expect(editor.locator("#status")).toHaveText("已插入并保存");
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${api}/chapters/${chapter.id}`)).json()).content,
      )
      .toContain("插件写入并保存。");
    await page.screenshot({
      path: test.info().outputPath("prompt-editor-toolbar.png"),
      animations: "disabled",
    });
    await editor.getByRole("button", { name: "撤销", exact: true }).click();
    await expect(editor.locator("#status")).toHaveText("已撤销，请保存");
    await expect(page.locator(".tiptap.ProseMirror").first()).not.toContainText("插件写入并保存。");
    await page.keyboard.press("Escape");
    await expect(editor).not.toBeVisible();
    await page.locator(".tiptap.ProseMirror").first().fill("工具栏同步：当前编辑器的新正文。");
    await page
      .locator('.editor-toolbar [data-plugin-slot="editor.toolbar"]')
      .getByRole("button", { name: "云同步", exact: true })
      .click();
    const toolbar = page.locator('[data-plugin-view="google-drive-sync/toolbar"]');
    await toolbar.getByRole("button", { name: "保存并同步本项目" }).click();
    await expect(toolbar.locator("#status")).toHaveText("同步完成");
    await expect
      .poll(async () => {
        const state = await (await page.request.get(`${backend}/_e2e/drive`)).json();
        return state.files.find(
          (file: { payload: { chapterId: string; content: string } }) =>
            file.payload.chapterId === chapter.id,
        )?.payload.content;
      })
      .toContain("工具栏同步：当前编辑器的新正文。");
    await page.screenshot({
      path: test.info().outputPath("drive-editor-toolbar.png"),
      animations: "disabled",
    });
    await page.keyboard.press("Escape");
    await expect(toolbar).not.toBeVisible();
    const switches = page.locator('[data-plugin-view="prompt-elements/switches"]');
    if (!(await switches.isVisible())) {
      await page.getByRole("button", { name: "Agent", exact: true }).first().click();
    }
    await expect(switches).toBeVisible();
    const combat = switches.getByRole("switch", { name: "战斗场景细节", exact: true });
    const previouslyChecked = await combat.getAttribute("aria-checked");
    await combat.click();
    await expect(combat).toHaveAttribute(
      "aria-checked",
      previouslyChecked === "true" ? "false" : "true",
    );
    await expect(switches.locator("#status")).toContainText("已保存");
    await expect(switches.locator("iframe")).toHaveCount(0);
    await page.screenshot({
      path: test.info().outputPath("prompt-above-composer.png"),
      animations: "disabled",
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/extensions/prompt-elements/rules?projectId=${project.id}`);
    const mobile = page.locator('[data-plugin-view="prompt-elements/rules"]');
    await expect(mobile.getByRole("button", { name: "预览注入结果" })).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy();
    expect(await mobile.evaluate((node) => node.scrollWidth <= node.clientWidth)).toBeTruthy();
  } finally {
    for (const id of examples) await page.request.delete(`${api}/plugins/${id}`);
    await page.request.delete(`${api}/projects/${project.id}`);
    await page.request.patch(`${api}/settings`, {
      data: { default_model: "", light_model: "", agent_bypass_tool_approval: false },
    });
    if (modelId) await page.request.delete(`${api}/models/${modelId}`);
    if (providerId) await page.request.delete(`${api}/model-providers/${providerId}`);
  }
});

test("management rejects raw and converted Mods and keeps native installation available", async ({
  page,
}) => {
  if (process.env.OPENFIC_E2E_PASSWORD)
    await page.request.post(`${api}/auth/login`, {
      data: { password: process.env.OPENFIC_E2E_PASSWORD },
    });
  await page.goto("/extensions");
  await page.getByRole("checkbox").check();
  for (const kind of ["raw", "converted"]) {
    const buffer = execFileSync("python3", [
      "-c",
      `import io,json,sys,zipfile
output=io.BytesIO()
with zipfile.ZipFile(output,'w') as archive:
 if sys.argv[1]=='raw':
  archive.writestr('.claude-plugin/plugin.json',json.dumps({'name':'removed-mod','version':'1.0.0'}))
  archive.writestr('hooks/hooks.json',json.dumps({'modules':['./register.mjs']}))
  archive.writestr('hooks/register.mjs','export function register() {}')
 else:
  archive.writestr('plugin.json',json.dumps({'id':'removed-mod','name':'Removed Mod','version':'1.0.0','api_version':1,'format':'claude-mod'}))
sys.stdout.buffer.write(output.getvalue())`,
      kind,
    ]);
    const pending = page.waitForResponse(
      (response) => response.request().method() === "POST" && response.url() === `${api}/plugins`,
    );
    await page.locator('input[type="file"]').setInputFiles({
      name: `${kind}.zip`,
      mimeType: "application/zip",
      buffer,
    });
    expect((await pending).status()).toBe(400);
    await expect(page.locator(".plugin-manager").getByRole("alert")).toContainText(
      kind === "raw" ? "plugin.json" : "format",
    );
    await expect(page.getByRole("button", { name: "安装插件包", exact: true })).toBeEnabled();
    await expect(page.locator('[data-plugin-id="removed-mod"]')).toHaveCount(0);
  }
});

test("React plugin uses the typed SDK package, inline styles, persistence and capability checks", async ({
  page,
}) => {
  if (process.env.OPENFIC_E2E_PASSWORD)
    await page.request.post(`${api}/auth/login`, {
      data: { password: process.env.OPENFIC_E2E_PASSWORD },
    });
  const directory = "/tmp/openfic-e2e-react-plugin";
  execFileSync("node", [`${root}frontend/e2e/build-react-plugin.mjs`, `${directory}/frontend`], {
    cwd: `${root}frontend`,
  });
  execFileSync("python3", [
    "-c",
    `from pathlib import Path;import json\np=Path('${directory}');p.mkdir(exist_ok=True);(p/'plugin.json').write_text(json.dumps({'id':'react-sdk-test','name':'React SDK fixture','version':'1.0.0','api_version':1,'capabilities':['storage','ui'],'views':[{'id':'react','title':'React SDK fixture','entry':'frontend/index.html','slot':'sidebar.extensions'}]}))`,
  ]);
  const zip = "/tmp/openfic-e2e-react-plugin.zip";
  execFileSync("python3", [`${root}examples/plugins/build_package.py`, directory, zip]);
  try {
    const installed = await page.request.post(`${api}/plugins`, {
      multipart: {
        trusted: "true",
        file: { name: "react.zip", mimeType: "application/zip", buffer: readFileSync(zip) },
      },
    });
    expect(installed.ok(), await installed.text()).toBeTruthy();
    expect(
      (
        await page.request.patch(`${api}/plugins/react-sdk-test/enabled`, {
          data: { enabled: true },
        })
      ).ok(),
    ).toBeTruthy();
    await page.goto("/extensions/react-sdk-test/react");
    const frame = page.frameLocator('iframe[title="React SDK fixture"]');
    await expect(frame.locator("p[role=status]")).toHaveText("Ready");
    await expect(frame.locator("main")).toHaveCSS("color", "rgb(12, 34, 56)");
    await frame.getByRole("button", { name: "Increment", exact: true }).click();
    await expect(frame.locator("output")).toHaveText("1");
    await page.reload();
    await expect(frame.locator("output")).toHaveText("1");
    await frame.getByRole("button", { name: "Try undeclared access" }).click();
    await expect(frame.locator("p[role=status]")).toContainText("projects.read");
  } finally {
    await page.request.delete(`${api}/plugins/react-sdk-test`);
  }
});
