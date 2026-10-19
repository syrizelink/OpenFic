import { expect, test } from "@playwright/test";

const backend = process.env.OPENFIC_E2E_BACKEND ?? "http://127.0.0.1:8021";

test.use({ video: "off" });

test("original navigation, settings plugin category and mobile shell still render", async ({
  page,
}) => {
  if (process.env.OPENFIC_E2E_PASSWORD)
    await page.request.post(`${backend}/api/v1/auth/login`, {
      data: { password: process.env.OPENFIC_E2E_PASSWORD },
    });
  const created = await page.request.post(`${backend}/api/v1/projects`, {
    multipart: { title: "导航回归临时项目" },
  });
  expect(created.ok()).toBeTruthy();
  const project = await created.json();
  try {
    const errors: string[] = [];
    const serverErrors: string[] = [];
    const loaded = new Set<string>();
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("response", (response) => {
      if (!response.url().includes("/api/v1/")) return;
      if (response.status() >= 500) serverErrors.push(response.url());
      if (response.ok()) loaded.add(response.url());
    });
    await page.goto("/");
    for (const route of ["/world-info", "/characters", "/prompt-chains", "/dashboard", "/"]) {
      await page.locator(`a[href="${route}"]`).first().click();
      await expect(page).toHaveURL(new RegExp(`${route === "/" ? "/" : route}$`));
      await expect(page.locator("#root")).not.toContainText("Unexpected Application Error");
      if (route === "/characters")
        await expect
          .poll(() => [...loaded].some((url) => url.includes("/characters")))
          .toBeTruthy();
      if (route === "/dashboard")
        await expect
          .poll(() => [...loaded].some((url) => url.includes("/dashboard/")))
          .toBeTruthy();
    }
    await page.getByRole("button", { name: "设置", exact: true }).click();
    const settings = page.getByRole("dialog", { name: "设置", exact: true });
    await expect(settings).toBeVisible();
    await settings.getByText("插件管理", { exact: true }).first().click();
    await expect(settings.getByRole("checkbox")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(settings).toHaveCount(0);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await expect(page.locator('a[href="/"]').first()).toBeAttached();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy();
    expect(serverErrors).toEqual([]);
    expect(errors).toEqual([]);
  } finally {
    await page.request.delete(`${backend}/api/v1/projects/${project.id}`);
  }
});
