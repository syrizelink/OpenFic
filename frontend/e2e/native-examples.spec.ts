import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const backend = process.env.OPENFIC_E2E_BACKEND ?? "http://127.0.0.1:8011";
const api = backend + "/api/v1";
const root = fileURLToPath(new URL("../../", import.meta.url));
const examples = [
  ["project-statistics", "overview", "项目统计"],
  ["google-drive-sync", "sync", "Google Drive 章节同步"],
  ["handoff-workflow", "workflow", "Handoff 写作工作流"],
  ["prompt-elements", "rules", "动态提示词元素"],
];
let projectId: string;
test.use({ video: "off" });

test.beforeAll(async ({ request }) => {
  if (process.env.OPENFIC_E2E_PASSWORD)
    await request.post(api + "/auth/login", {
      data: { password: process.env.OPENFIC_E2E_PASSWORD },
    });
  const project = await request.post(api + "/projects", {
    multipart: { title: "原生 UI 效果验证项目" },
  });
  expect(project.ok()).toBeTruthy();
  projectId = (await project.json()).id;
  const volumes = await (await request.get(`${api}/projects/${projectId}/volumes`)).json();
  expect(
    (
      await request.post(`${api}/projects/${projectId}/chapters`, {
        data: {
          volume_id: volumes[0].id,
          title: "序章：山谷来信",
          content: "旅人抵达山谷。",
          word_count: 2400,
        },
      })
    ).ok(),
  ).toBeTruthy();
  for (const [id] of examples) {
    await request.delete(`${api}/plugins/${id}`);
    const path = `/tmp/openfic-native-${id}.zip`;
    execFileSync("python3", [
      root + "examples/plugins/build_package.py",
      root + "examples/plugins/" + id,
      path,
    ]);
    expect(
      (
        await request.post(api + "/plugins", {
          multipart: {
            trusted: "true",
            file: { name: id + ".zip", mimeType: "application/zip", buffer: readFileSync(path) },
          },
        })
      ).ok(),
    ).toBeTruthy();
    expect(
      (await request.patch(`${api}/plugins/${id}/enabled`, { data: { enabled: true } })).ok(),
    ).toBeTruthy();
  }
});

test.afterAll(async ({ request }) => {
  for (const [id] of examples) await request.delete(`${api}/plugins/${id}`);
  if (projectId) await request.delete(`${api}/projects/${projectId}`);
});

for (const [id, viewId, title] of examples) {
  test(`${id}: native styling, usable controls, desktop and mobile layout`, async ({
    page,
  }, info) => {
    if (process.env.OPENFIC_E2E_PASSWORD)
      await page.request.post(api + "/auth/login", {
        data: { password: process.env.OPENFIC_E2E_PASSWORD },
      });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width: 1600, height: 1000 });
    await page.goto(`/extensions/${id}/${viewId}?projectId=${projectId}`);
    const view = page.locator(`[data-plugin-view="${id}/${viewId}"]`);
    await expect(view.locator(".example-title")).toHaveText(title);
    await expect(view.locator(".example-title")).toBeVisible();
    await expect(view.locator("iframe")).toHaveCount(0);
    await expect(view.locator(".example-title")).toHaveCSS(
      "color",
      await view.evaluate((node) => {
        const sample = document.createElement("span");
        sample.style.color = "var(--accent-11)";
        node.append(sample);
        const color = getComputedStyle(sample).color;
        sample.remove();
        return color;
      }),
    );
    if (id === "project-statistics") {
      await expect(view.getByTestId("metric-words")).toContainText("2,400");
      expect(
        await view
          .locator("#metrics")
          .evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(" ").length),
      ).toBe(4);
    }
    if (id === "google-drive-sync") {
      await view.getByLabel("Access token").fill("test-drive-token");
      await view.getByRole("button", { name: "安全保存令牌" }).click();
      await expect(view.locator("#connection")).toHaveText("已连接");
      await expect(view.getByLabel("Access token")).toHaveValue("");
      await view.getByRole("button", { name: "预览变化" }).click();
      await expect(view.locator("#status")).toContainText("变化预览完成");
      await view.getByRole("button", { name: "立即同步", exact: true }).click();
      await expect(view.locator("#report")).toContainText("上传 1");
    }
    if (id === "handoff-workflow") {
      await view.getByRole("button", { name: "演示交接（不调用模型）" }).click();
      await expect(view.locator("#output")).toContainText("审核通过");
      const download = page.waitForEvent("download");
      await view.getByRole("button", { name: "导出结果" }).click();
      expect((await download).suggestedFilename()).toBe("handoff-result.json");
    }
    if (id === "prompt-elements") {
      await view.getByRole("textbox", { name: "元素定义", exact: true }).fill("{bad JSON");
      await view.getByRole("button", { name: "保存规则", exact: true }).click();
      await expect(view.getByRole("alert")).toBeVisible();
      await view.getByRole("button", { name: "使用全局默认" }).click();
      await expect(view.getByRole("textbox", { name: "元素定义", exact: true })).toHaveValue(
        /consistency/,
      );
      await view.getByRole("button", { name: "预览注入结果" }).click();
      await expect(view.locator("#matched")).toContainText("combat-detection");
      const download = page.waitForEvent("download");
      await view.getByRole("button", { name: "导出配置" }).click();
      expect((await download).suggestedFilename()).toBe("prompt-elements.json");
    }
    for (const size of ["desktop", "mobile"] as const) {
      if (size === "mobile") {
        await page.setViewportSize({ width: 390, height: 844 });
        await page.reload();
        await expect(view.locator(".example-title")).toBeVisible();
        await expect(page.locator(".mobile-sidebar-sheet")).toHaveAttribute("data-open", "false");
        await expect
          .poll(() =>
            page
              .locator(".mobile-sidebar-sheet")
              .evaluate((node) => node.getBoundingClientRect().right),
          )
          .toBeLessThanOrEqual(1);
        if (id === "project-statistics")
          await view.getByRole("button", { name: "刷新", exact: true }).click();
        if (id === "google-drive-sync") {
          await view.getByRole("button", { name: "预览变化", exact: true }).click();
          await expect(view.locator("#status")).toContainText("变化预览完成");
        }
        if (id === "handoff-workflow") {
          await view.getByRole("button", { name: "演示交接（不调用模型）" }).click();
          await expect(view.locator("#status")).toContainText("演示完成");
        }
        if (id === "prompt-elements") {
          await view.getByRole("button", { name: "预览注入结果" }).click();
          await expect(view.locator("#status")).toContainText("预览完成");
        }
      }
      await expect
        .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
        .toBeTruthy();
      await expect
        .poll(() => view.evaluate((node) => node.scrollWidth <= node.clientWidth + 1))
        .toBeTruthy();
      if (size === "mobile" && id === "project-statistics")
        expect(
          await view
            .locator("#metrics")
            .evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(" ").length),
        ).toBe(2);
      await view.locator(".example-title").scrollIntoViewIfNeeded();
      const screenshot = await page.screenshot({
        path: info.outputPath(`${id}-${size}.png`),
        animations: "disabled",
      });
      await info.attach(`${id}-${size}`, { body: screenshot, contentType: "image/png" });
    }
    await page.reload();
    await expect(view.locator(".example-page")).toBeVisible();
    expect(errors).toEqual([]);
  });
}
