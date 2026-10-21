import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const backend = process.env.OPENFIC_E2E_BACKEND ?? "http://127.0.0.1:8041";
const api = backend + "/api/v1";
const source = process.env.OPENFIC_E2E_PLUGIN_SOURCE;
test.use({ video: "off" });
async function choice(page: Page, name: string, value: string) {
  await page.getByRole("combobox", { name, exact: true }).click();
  await page.getByRole("option", { name: value, exact: true }).click();
}
async function state(page: Page) {
  const response = await page.request.get(`${api}/plugins/development`);
  expect(response.ok()).toBeTruthy();
  return response.json();
}
async function records(page: Page) {
  const response = await page.request.get(`${api}/plugins/devtools-demo/inspector`);
  expect(response.ok()).toBeTruthy();
  return (await response.json()).entries as {
    sequence: number;
    kind: string;
    method: string;
    status: string;
    [key: string]: unknown;
  }[];
}

test("devtools: real native previews, props/CSS, permissions, secret redaction, mobile and export", async ({
  page,
}, info) => {
  expect((await state(page)).enabled).toBe(true);
  await page.request.put(`${api}/plugins/devtools-demo/settings`, {
    data: { settings: { apiKey: "private-devtools-e2e-secret" } },
  });
  for (const key of ["count", "css-warning", "position"])
    await page.request.post(`${api}/plugins/devtools-demo/rpc`, {
      data: { method: "sdk.storage.delete", params: { key } },
    });
  await page.goto("/extensions");
  await page.getByRole("link", { name: "插件开发工具", exact: true }).click();
  const preview = page.frameLocator('iframe[title="插件独立视口预览"]');
  await expect(preview.getByRole("heading", { name: "原生 SDK 开发示例" })).toBeVisible();
  await preview.getByRole("button", { name: "增加计数", exact: true }).click();
  await expect(preview.locator("#demo-count")).toHaveText("计数：1");
  await expect(page.locator('[data-inspector="tree"]')).toContainText("onPress");
  await preview.getByRole("button", { name: "验证密钥脱敏" }).click();
  await expect
    .poll(async () => (await records(page)).some((entry) => entry.method === "secrets.set"))
    .toBe(true);
  expect(JSON.stringify(await records(page))).not.toContain("private-devtools-e2e-secret");
  await preview.getByRole("button", { name: "触发权限错误" }).click();
  await expect(preview.getByRole("alert")).toContainText("projects.read");
  await page.getByRole("button", { name: "调用 / 事件", exact: true }).click();
  await choice(page, "记录筛选", "错误");
  await expect(page.locator(".plugin-devtools-traces")).toContainText("api.request");
  await preview.getByRole("button", { name: "触发 CSS 诊断" }).click();
  await page.getByRole("button", { name: "CSS", exact: true }).click();
  await expect(page.locator('[data-inspector="css"]')).toContainText("@import");
  await expect(page.locator('[data-inspector="css"] .plugin-devtools-json').last()).toContainText(
    "data-plugin-style-root",
  );
  await expect(
    page.locator('[data-inspector="css"] .plugin-devtools-json').last(),
  ).not.toContainText("@import");
  await page.getByText("预览上下文", { exact: true }).click();
  await page.getByRole("textbox", { name: "预览上下文 JSON" }).fill("[]");
  await page.getByRole("button", { name: "应用上下文" }).click();
  await expect(page.getByRole("alert")).toContainText("JSON 对象");
  await page
    .getByRole("textbox", { name: "预览上下文 JSON" })
    .fill('{"projectId":"preview-project","custom":"context-example"}');
  await page.getByRole("button", { name: "应用上下文" }).click();
  await expect(preview.getByRole("heading", { name: "原生 SDK 开发示例" })).toBeVisible();
  await choice(page, "视口", "手机 · 390px");
  await choice(page, "主题", "深色");
  await expect(page.locator('iframe[title="插件独立视口预览"]')).toHaveCSS("width", "390px");
  await expect(preview.locator(".plugin-development-canvas")).toHaveClass(/dark/);
  expect(
    await preview.locator(".plugin-development-canvas").evaluate((node) => {
      const values = getComputedStyle(node)
        .backgroundColor.match(/[\d.]+/g)
        ?.map(Number);
      return values && values[0] < 100 && values[1] < 100 && values[2] < 100;
    }),
  ).toBeTruthy();
  await choice(page, "视图 / 插槽", "工具栏示例 · editor.toolbar");
  await preview.getByRole("button", { name: "工具栏示例", exact: true }).click();
  await expect(preview.locator("#demo-count")).toHaveText("计数：1");
  await choice(page, "视图 / 插槽", "浮层示例 · app.overlay");
  const panel = preview.locator(".plugin-floating-panel");
  await expect(panel).toBeVisible();
  const iframeBounds = (await page.locator('iframe[title="插件独立视口预览"]').boundingBox())!;
  const panelBounds = (await panel.boundingBox())!;
  expect(panelBounds.x).toBeGreaterThanOrEqual(iframeBounds.x);
  expect(panelBounds.x + panelBounds.width).toBeLessThanOrEqual(iframeBounds.x + 391);
  await page.getByRole("button", { name: "组件树 / Props" }).click();
  await expect(page.locator('[data-inspector="tree"]')).toContainText("FloatingPanel");
  await expect(page.locator('[data-inspector="tree"]')).toContainText("计数：1");
  await page.locator(".plugin-devtools-layout").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: info.outputPath("plugin-devtools-mobile-preview.png"),
    animations: "disabled",
  });
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出诊断" }).click();
  const file = await download;
  await file.saveAs(info.outputPath("diagnostics.json"));
  expect(readFileSync(info.outputPath("diagnostics.json"), "utf8")).not.toContain(
    "private-devtools-e2e-secret",
  );
  const cursor = Math.max(...(await records(page)).map((entry) => entry.sequence));
  await page.getByRole("button", { name: "清空记录" }).click();
  await expect
    .poll(async () => (await records(page)).every((entry) => entry.sequence > cursor))
    .toBe(true);
});

test("devtools: source watch preserves state/version, rejects bad props, rolls back activation and reloads iframe assets", async ({
  page,
}, info) => {
  test.skip(!source, "Requires a disposable source directory served by openfic plugin dev");
  await page.request.post(`${api}/plugins/devtools-demo/rpc`, {
    data: { method: "sdk.storage.delete", params: { key: "iframe-count" } },
  });
  const entryFile = path.join(source!, "main.py");
  const viewFile = path.join(source!, "views.py");
  const htmlFile = path.join(source!, "panel/index.html");
  if (path.resolve(source!).endsWith("/examples/plugins/devtools-demo"))
    throw new Error("Use a disposable copy, not the tracked example source");
  const entry = readFileSync(entryFile, "utf8");
  const original = readFileSync(viewFile, "utf8");
  const html = readFileSync(htmlFile, "utf8");
  try {
    await page.goto("/extensions/devtools?pluginId=devtools-demo");
    const preview = page.frameLocator('iframe[title="插件独立视口预览"]');
    await expect(preview.locator("#demo-count")).toHaveText("计数：1");
    const revision = (await state(page)).revision;
    writeFileSync(viewFile, original.replace("原生 SDK 开发示例", "热重载后的原生组件"));
    await expect
      .poll(async () => (await state(page)).revision, { timeout: 20000 })
      .toBeGreaterThan(revision);
    await expect(preview.getByRole("heading", { name: "热重载后的原生组件" })).toBeVisible();
    await expect(preview.locator("#demo-count")).toHaveText("计数：1");
    const version = (await (await page.request.get(`${api}/plugins`)).json()).plugins.find(
      (item: { id: string }) => item.id === "devtools-demo",
    ).version;
    expect(version).toBe("1.1.0");
    writeFileSync(viewFile, original.replace('size="4"', 'size="99"'));
    await expect.poll(async () => (await state(page)).status, { timeout: 20000 }).toBe("error");
    await expect(page.locator('[data-diagnostic-code="ui.value"]')).toBeVisible();
    await expect(preview.getByRole("heading", { name: "热重载后的原生组件" })).toBeVisible();
    writeFileSync(viewFile, original);
    writeFileSync(entryFile, entry + '\nraise RuntimeError("E2E activation failure")\n');
    await expect
      .poll(
        async () =>
          (await state(page)).diagnostics.some(
            (entry: { code: string }) => entry.code === "development.reload",
          ),
        { timeout: 20000 },
      )
      .toBe(true);
    await expect(preview.getByRole("heading", { name: "热重载后的原生组件" })).toBeVisible();
    writeFileSync(entryFile, entry);
    writeFileSync(viewFile, original);
    await expect.poll(async () => (await state(page)).status, { timeout: 20000 }).toBe("ready");
    await expect(preview.getByRole("heading", { name: "原生 SDK 开发示例" })).toBeVisible();
    await choice(page, "视图 / 插槽", "自带前端示例 · settings.plugins");
    const inner = preview.frameLocator('iframe[title="自带前端示例"]');
    await expect(inner.locator("#value")).toContainText("iframe 计数");
    await inner.getByRole("button", { name: "增加 iframe 计数" }).click();
    await expect(inner.locator("#value")).toHaveText("iframe 计数：1");
    writeFileSync(htmlFile, html.replace("<h1>自带前端示例</h1>", "<h1>热重载后的 iframe</h1>"));
    await expect(inner.getByRole("heading", { name: "热重载后的 iframe" })).toBeVisible({
      timeout: 20000,
    });
    await expect(inner.locator("#value")).toHaveText("iframe 计数：1");
    await choice(page, "主题", "深色");
    await expect(inner.locator("html")).toHaveAttribute("data-theme", "dark");
    await inner.getByRole("button", { name: "触发前端异常" }).click();
    await expect
      .poll(async () =>
        (await records(page)).some(
          (entry) =>
            entry.kind === "frontend.iframe" &&
            entry.method === "runtime.error" &&
            String(entry.error).includes("Intentional iframe"),
        ),
      )
      .toBe(true);
    expect(JSON.stringify(await records(page))).not.toContain("private-devtools-e2e-secret");
    await page.getByRole("button", { name: "调用 / 事件" }).click();
    await choice(page, "记录筛选", "错误");
    await expect(page.locator(".plugin-devtools-traces")).toContainText("runtime.error");
    await page.screenshot({
      path: info.outputPath("plugin-devtools-iframe-error.png"),
      animations: "disabled",
    });
  } finally {
    writeFileSync(entryFile, entry);
    writeFileSync(viewFile, original);
    writeFileSync(htmlFile, html);
  }
});
