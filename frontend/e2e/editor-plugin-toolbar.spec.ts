import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const backend = process.env.OPENFIC_E2E_BACKEND ?? "http://127.0.0.1:8021";
const api = backend + "/api/v1";
const root = fileURLToPath(new URL("../../", import.meta.url));
test.use({ video: "off" });

async function geometry(page: Page) {
  return Promise.all([
    page.locator(".editor-toolbar").boundingBox(),
    page.locator(".tiptap-editor-wrapper").boundingBox(),
  ]);
}

test("editor slots stay in the toolbar: native/Lucide, legacy portals, selections, notes and touch", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const zip = "/tmp/openfic-editor-toolbar.zip";
  execFileSync("python3", [
    root + "examples/plugins/build_package.py",
    root + "frontend/e2e/fixtures/plugin-editor-toolbar",
    zip,
  ]);
  await page.request.delete(`${api}/plugins/editor-toolbar-test`);
  const response = await page.request.post(api + "/projects", {
    multipart: { title: "工具栏布局验证" },
  });
  expect(response.ok()).toBeTruthy();
  const project = await response.json();
  try {
    const volumes = await (await page.request.get(`${api}/projects/${project.id}/volumes`)).json();
    const chapter = await (
      await page.request.post(`${api}/projects/${project.id}/chapters`, {
        data: { volume_id: volumes[0].id, title: "工具栏章节", content: "起点终点", word_count: 4 },
      })
    ).json();
    const note = await (
      await page.request.post(`${api}/projects/${project.id}/notes`, {
        data: { title: "工具栏笔记", content: "笔记正文" },
      })
    ).json();
    await page.goto(`/projects/${project.id}`);
    await page.getByText("工具栏章节", { exact: true }).first().click();
    const content = page.locator(".chapter-editor-content .tiptap");
    await expect(content).toHaveText("起点终点");
    const original = await geometry(page);
    const install = await page.request.post(api + "/plugins", {
      multipart: {
        trusted: "true",
        file: { name: "toolbar.zip", mimeType: "application/zip", buffer: readFileSync(zip) },
      },
    });
    expect(install.ok(), await install.text()).toBeTruthy();
    expect(
      (
        await page.request.patch(`${api}/plugins/editor-toolbar-test/enabled`, {
          data: { enabled: true },
        })
      ).ok(),
    ).toBeTruthy();
    const actions = page.locator(".editor-toolbar .editor-plugin-actions");
    const trigger = actions.getByRole("button", { name: "浮层测试", exact: true });
    await expect(trigger).toBeVisible();
    expect(await geometry(page)).toEqual(original);
    await expect(actions.getByRole("button")).toHaveCount(13);
    expect(
      await actions.evaluate((el) => el.scrollWidth > el.clientWidth && el.clientWidth <= 200),
    ).toBeTruthy();
    await expect(trigger.locator('svg[data-lucide="CloudUpload"]')).toHaveCount(1);
    await expect(page.locator(".plugin-slot-content")).toHaveCount(0);
    await content.click();
    await content.press("Home");
    await content.press("ArrowRight");
    await content.press("ArrowRight");
    await trigger.focus();
    await trigger.press("Enter");
    const native = page.locator('[data-plugin-view="editor-toolbar-test/native"]');
    await expect(native.locator("#kind")).toHaveText("chapter");
    await expect(native.locator("#entity")).toHaveText(chapter.id);
    await expect(native.getByRole("img", { name: "声明式云图标" })).toHaveAttribute(
      "data-lucide",
      "CloudUpload",
    );
    await expect(native.getByRole("img")).toHaveAttribute("stroke-width", "1.5");
    expect(await native.evaluate((el) => !el.closest(".editor-toolbar"))).toBeTruthy();
    const input = native.getByLabel("浮层输入");
    await input.fill("中间");
    await expect(input).toBeFocused();
    await expect(input).toHaveValue("中间");
    await native.getByRole("button", { name: "插入选区" }).click();
    await expect(native.locator("#status")).toHaveText("保存完成");
    await expect(content).toHaveText("起点中间终点");
    await expect
      .poll(async () =>
        String(
          (await (await page.request.get(`${api}/chapters/${chapter.id}`)).json()).content,
        ).replace(/\s/g, ""),
      )
      .toContain("起点中间终点");
    expect(await geometry(page)).toEqual(original);
    await page.screenshot({ path: info.outputPath("toolbar-popover.png"), animations: "disabled" });
    await page.keyboard.press("Escape");
    await expect(native).not.toBeVisible();
    await expect(trigger).toBeFocused();
    await actions.getByRole("button", { name: "旧上下文", exact: true }).click();
    await expect(
      page.frameLocator('iframe[title="旧上下文"]').getByText("Legacy floating view"),
    ).toBeVisible();
    expect(await geometry(page)).toEqual(original);
    await page
      .getByRole("button", { name: /旧上下文$/ })
      .last()
      .click();
    await actions.getByRole("button", { name: "旧面板", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "旧面板", exact: true });
    await expect(dialog).toBeVisible();
    expect(await geometry(page)).toEqual(original);
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
    await page.getByText("笔记", { exact: true }).first().click();
    await page.getByText("工具栏笔记", { exact: true }).first().click();
    await expect(page.locator(".markdown-editor-content .tiptap")).toHaveText("笔记正文");
    const noteGeometry = await geometry(page);
    await trigger.click();
    await expect(native.locator("#kind")).toHaveText("note");
    await expect(native.locator("#entity")).toHaveText(note.id);
    expect(await geometry(page)).toEqual(noteGeometry);
    await page.keyboard.press("Escape");

    // Mobile toolbar follows the keyboard; emulate visualViewport shrink as a real keyboard does.
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await expect(page.locator(".markdown-editor-content .tiptap")).toHaveText("笔记正文");
    await page.evaluate(() => {
      Object.defineProperty(window.visualViewport!, "height", {
        configurable: true,
        get: () => 510,
      });
      window.visualViewport!.dispatchEvent(new Event("resize"));
    });
    await expect(trigger).toBeVisible();
    await trigger.dispatchEvent("pointerdown", { pointerType: "touch", bubbles: true });
    await trigger.click();
    await expect(native).toBeVisible();
    await input.dispatchEvent("pointerdown", { pointerType: "touch", bubbles: true });
    await input.fill("触摸输入");
    await expect(input).toBeFocused();
    const box = await page.getByRole("dialog", { name: "浮层测试", exact: true }).boundingBox();
    expect(box).toBeTruthy();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(390);
    await page.screenshot({ path: info.outputPath("toolbar-mobile.png"), animations: "disabled" });
    await page.keyboard.press("Escape");
    expect(
      (
        await page.request.patch(`${api}/plugins/editor-toolbar-test/enabled`, {
          data: { enabled: false },
        })
      ).ok(),
    ).toBeTruthy();
    await expect(actions).toHaveCount(0);
    expect(errors).toEqual([]);
  } finally {
    await page.request.delete(`${api}/plugins/editor-toolbar-test`);
    await page.request.delete(`${api}/projects/${project.id}`);
  }
});
