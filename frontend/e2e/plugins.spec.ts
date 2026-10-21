import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const backend = process.env.OPENFIC_E2E_BACKEND ?? "http://127.0.0.1:8000";
const root = fileURLToPath(new URL("../../", import.meta.url));
const packagePath = `${root}examples/plugins/dist/project-statistics-1.2.0.zip`;
test.use({ video: "off" });

test("install a unified package, render statistics, configure, disable and uninstall", async ({
  page,
}) => {
  execFileSync("python3", [
    `${root}examples/plugins/build_package.py`,
    `${root}examples/plugins/project-statistics`,
    packagePath,
  ]);
  if (process.env.OPENFIC_E2E_PASSWORD) {
    const login = await page.request.post(`${backend}/api/v1/auth/login`, {
      data: { password: process.env.OPENFIC_E2E_PASSWORD },
    });
    expect(login.ok()).toBeTruthy();
  }
  const existing = await page.request.get(`${backend}/api/v1/plugins`);
  for (const plugin of (await existing.json()).plugins) {
    if (plugin.id === "project-statistics")
      await page.request.delete(`${backend}/api/v1/plugins/${plugin.id}`);
  }
  const created = await page.request.post(`${backend}/api/v1/projects`, {
    multipart: { title: "插件统计验证" },
  });
  expect(created.status()).toBe(201);
  const project = await created.json();
  try {
    const volumes = await (
      await page.request.get(`${backend}/api/v1/projects/${project.id}/volumes`)
    ).json();
    const chapter = await page.request.post(`${backend}/api/v1/projects/${project.id}/chapters`, {
      data: { volume_id: volumes[0].id, title: "第一章", content: "已保存的章节", word_count: 400 },
    });
    expect(chapter.status()).toBe(201);
    await page.goto("/extensions");
    await expect(page.getByRole("heading", { name: "插件管理", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "安装插件包", exact: true })).toBeDisabled();
    await page.getByRole("checkbox").check();
    await page.locator('input[type="file"]').setInputFiles(packagePath);
    const card = page.locator('[data-plugin-id="project-statistics"]');
    await expect(card.getByText("已停用", { exact: true })).toBeVisible();
    await card.getByRole("button", { name: "启用", exact: true }).click();
    await expect(card.getByText("已启用", { exact: true })).toBeVisible();
    const region = page.getByRole("navigation", { name: "扩展", exact: true });
    await region.getByRole("link", { name: "项目统计", exact: true }).click();
    const view = page.locator('[data-plugin-view="project-statistics/overview"]');
    await expect(view.locator("iframe")).toHaveCount(0);
    await expect(view.getByRole("heading", { name: "项目统计", exact: true }).last()).toBeVisible();
    await view.locator('[data-plugin-component="ProjectSelectField"]').getByRole("textbox").click();
    await page.getByText("插件统计验证", { exact: true }).last().click();
    await expect(view.getByTestId("metric-words").locator("strong")).toHaveText("400");
    await expect(view.locator("#volume-body")).toContainText("400");
    await page.getByRole("link", { name: "插件管理", exact: true }).last().click();
    await card.getByText("插件配置", { exact: true }).click();
    await card.getByLabel("目标字数 / Target words").fill("800");
    await card.getByRole("button", { name: "保存配置", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("配置已保存");
    await region.getByRole("link", { name: "项目统计", exact: true }).click();
    await view.locator('[data-plugin-component="ProjectSelectField"]').getByRole("textbox").click();
    await page.getByText("插件统计验证", { exact: true }).last().click();
    await expect(view.locator("#goal")).toContainText("50%");
    await page.reload();
    await expect(view.getByRole("heading", { name: "项目统计", exact: true }).last()).toBeVisible();
    await page.getByRole("link", { name: "插件管理", exact: true }).last().click();
    await card.getByRole("button", { name: "停用", exact: true }).click();
    await expect(region.getByRole("link", { name: "项目统计", exact: true })).toHaveCount(0);
    await card.getByRole("button", { name: "日志", exact: true }).click();
    await expect(page.locator(".plugin-logs")).toContainText("Plugin disabled");
    await card.getByRole("button", { name: "卸载", exact: true }).click();
    await page.getByRole("button", { name: "确认卸载", exact: true }).click();
    await expect(card).toHaveCount(0);
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByRole("heading", { name: "插件管理", exact: true })).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBeTruthy();
  } finally {
    await page.request.delete(`${backend}/api/v1/plugins/project-statistics`);
    await page.request.delete(`${backend}/api/v1/projects/${project.id}`);
  }
});
