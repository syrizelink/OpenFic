import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const backend = process.env.OPENFIC_E2E_BACKEND ?? "http://127.0.0.1:8011";
const api = `${backend}/api/v1`;
const root = fileURLToPath(new URL("../../", import.meta.url));
test.use({ video: "off" });

test("one plugin mixes native Radix controls and legacy iframe, with safe rendering and persisted actions", async ({
  page,
}) => {
  if (process.env.OPENFIC_E2E_PASSWORD)
    await page.request.post(`${api}/auth/login`, {
      data: { password: process.env.OPENFIC_E2E_PASSWORD },
    });
  const zip = "/tmp/openfic-declarative-e2e.zip";
  execFileSync("python3", [
    `${root}examples/plugins/build_package.py`,
    `${root}frontend/e2e/fixtures/plugin-declarative`,
    zip,
  ]);
  await page.request.delete(`${api}/plugins/declarative-test`);
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  try {
    const installed = await page.request.post(`${api}/plugins`, {
      multipart: {
        trusted: "true",
        file: { name: "mixed.zip", mimeType: "application/zip", buffer: readFileSync(zip) },
      },
    });
    expect(installed.ok(), await installed.text()).toBeTruthy();
    expect(
      (
        await page.request.patch(`${api}/plugins/declarative-test/enabled`, {
          data: { enabled: true },
        })
      ).ok(),
    ).toBeTruthy();
    await page.goto("/extensions/declarative-test/native");
    const native = page.locator('[data-plugin-view="declarative-test/native"]');
    await expect(native).toHaveAttribute("data-renderer", "declarative");
    await expect(page.locator("iframe")).toHaveCount(0);
    await expect(native).toContainText("<img src=x onerror=alert(1)>");
    await expect(native.locator("img,script")).toHaveCount(0);
    await expect(native.getByText("Unsafe URL", { exact: true })).not.toHaveAttribute("href");
    await expect(native.getByRole("button", { name: "Increment" })).toHaveClass(/rt-Button/);
    await native.getByRole("button", { name: "Increment" }).click();
    await expect(native).toContainText("Count: 1");
    await native
      .getByRole("textbox", { name: "Name", exact: true })
      .pressSequentially("native", { delay: 0 });
    await expect(native.getByRole("textbox", { name: "Name", exact: true })).toHaveValue("native");
    await expect(native).toContainText("Name: native");
    await page.unroute("**/plugins/declarative-test/views/native/action");
    await native.getByRole("textbox", { name: "Name", exact: true }).press("Enter");
    await expect(native).toContainText("Submitted: native");
    await native.getByRole("combobox", { name: "Mode" }).click();
    await page.getByRole("option", { name: "Second" }).click();
    await expect(native).toContainText("Mode: two");
    await native.getByRole("checkbox", { name: "Enabled" }).click();
    await expect(native.getByRole("checkbox", { name: "Enabled" })).toBeChecked();
    await native.getByRole("switch", { name: "Automatic" }).click();
    await expect(native.getByRole("switch", { name: "Automatic" })).toBeChecked();
    // Host-side data invalidation refreshes declarative state without navigation.
    expect(
      (
        await page.request.post(`${api}/plugins/declarative-test/rpc`, {
          data: {
            method: "sdk.storage.set",
            params: {
              key: "state",
              value: { count: 7, name: "persisted", mode: "two", enabled: true, automatic: true },
            },
          },
        })
      ).ok(),
    ).toBeTruthy();
    await page.evaluate(() =>
      window.dispatchEvent(
        new CustomEvent("openfic:plugin-event", { detail: { event: "ui.invalidate", data: {} } }),
      ),
    );
    await expect(native).toContainText("Count: 7");
    await page.reload();
    await expect(native.getByRole("textbox", { name: "Name", exact: true })).toHaveValue(
      "persisted",
    );
    await expect(native.getByRole("checkbox", { name: "Enabled" })).toBeChecked();
    await page.goto("/extensions/declarative-test/legacy");
    await expect(
      page.frameLocator('iframe[title="Legacy iframe"]').getByText("Legacy iframe works"),
    ).toBeVisible();
    await expect(page.locator('iframe[title="Legacy iframe"]')).toHaveAttribute(
      "sandbox",
      "allow-scripts",
    );
    expect(pageErrors).toEqual([]);
  } finally {
    await page.request.delete(`${api}/plugins/declarative-test`);
  }
});
