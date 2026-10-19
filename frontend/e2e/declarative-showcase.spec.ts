import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const backend = process.env.OPENFIC_E2E_BACKEND ?? "http://127.0.0.1:8011";
const api = backend + "/api/v1";
const root = fileURLToPath(new URL("../../", import.meta.url));
const plugin = "declarative-showcase";
test.use({ video: "off" });
async function install(page: Page) {
  if (process.env.OPENFIC_E2E_PASSWORD)
    await page.request.post(api + "/auth/login", {
      data: { password: process.env.OPENFIC_E2E_PASSWORD },
    });
  execFileSync("python3", [
    root + "examples/plugins/build_package.py",
    root + "examples/plugins/" + plugin,
    "/tmp/openfic-showcase.zip",
  ]);
  await page.request.delete(api + "/plugins/" + plugin);
  const response = await page.request.post(api + "/plugins", {
    multipart: {
      trusted: "true",
      file: {
        name: "showcase.zip",
        mimeType: "application/zip",
        buffer: readFileSync("/tmp/openfic-showcase.zip"),
      },
    },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  expect(
    (
      await page.request.patch(api + "/plugins/" + plugin + "/enabled", { data: { enabled: true } })
    ).ok(),
  ).toBeTruthy();
}

test("native catalogue, project data, Radix events, responsive props and scoped portals", async ({
  page,
}) => {
  await install(page);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let projectId = "",
    providerId = "",
    modelId = "";
  try {
    const project = await page.request.post(api + "/projects", {
      multipart: { title: "UI Selector Project" },
    });
    expect(project.ok()).toBeTruthy();
    projectId = (await project.json()).id;
    const provider = await page.request.post(api + "/model-providers", {
      multipart: {
        name: "UI Provider",
        provider_type: "openai_compatible",
        url: backend + "/_e2e/provider/v1",
        api_key: "dummy",
      },
    });
    expect(provider.ok()).toBeTruthy();
    providerId = (await provider.json()).id;
    const model = await page.request.post(api + "/models", {
      data: {
        name: "UI Configured Model",
        model_id: "sdk-test-model",
        provider_id: providerId,
        context_length: 32000,
      },
    });
    expect(model.ok()).toBeTruthy();
    modelId = (await model.json()).id;
    await page.goto("/extensions/" + plugin + "/showcase");
    const view = page.locator('[data-plugin-view="declarative-showcase/showcase"]');
    await expect(view.getByRole("heading", { name: "Native UI showcase" }).last()).toHaveCSS(
      "color",
      "rgb(109, 40, 217)",
    );
    await expect(
      view.locator('[data-plugin-component="Spinner"][data-component-source="project"]').first(),
    ).toBeVisible();
    await expect(
      view.locator('[data-plugin-component="Spinner"][data-component-source="radix"]'),
    ).toBeVisible();
    await expect(view.getByRole("progressbar", { name: "Project progress" })).toHaveAttribute(
      "aria-valuenow",
      "70",
    );
    await expect(view.getByText("Prefix", { exact: true })).toBeVisible();
    await expect(view.locator("iframe")).toHaveCount(0);
    await page.getByRole("button", { name: "Native UI status", exact: true }).click();
    const status = page.getByTestId("showcase-status");
    await expect(status).toHaveCSS("color", "rgb(14, 116, 144)");
    const statusAnimation = await status.evaluate((el) => getComputedStyle(el).animationName);
    await expect(view.locator(".showcase-title")).toHaveCSS("letter-spacing", "1px");
    await expect(view.locator(".showcase-code")).toHaveAttribute("data-accent-color", "violet");
    await expect(view.locator(".showcase-code")).toHaveCSS("font-size", "14px");
    const state = view.getByTestId("state");
    await view.locator('[data-plugin-component="ModelIdSelect"]').getByRole("button").click();
    await page.getByText("UI Configured Model", { exact: true }).click();
    await expect(state).toContainText(modelId);
    await view.locator('[data-plugin-component="ProjectSelectField"]').getByRole("textbox").click();
    await page.getByText("UI Selector Project", { exact: true }).click();
    await expect(state).toContainText(projectId);
    await view.getByRole("textbox", { name: "Word target" }).fill("1200");
    await expect(state).toContainText('"unit": "1200"');
    await view
      .getByRole("textbox", { name: "Description", exact: true })
      .fill("Real multiline input");
    await expect(state).toContainText("Real multiline input");
    await expect(view.getByTestId("search-control")).toHaveAttribute(
      "aria-label",
      "Search control",
    );
    await view.locator('[data-slot="searchable-select-trigger"]').click();
    await page.locator('[data-slot="searchable-select-item"]').filter({ hasText: "Beta" }).click();
    await expect(state).toContainText('"search": "beta"');
    await view.getByRole("spinbutton").fill("6");
    await view.getByRole("spinbutton").press("Enter");
    await expect(state).toContainText('"stepper": 6');
    const grid = view.getByTestId("responsive-grid");
    expect(
      await grid.evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(" ").length),
    ).toBe(2);
    await view.getByRole("checkbox", { name: "First choice" }).click();
    await expect(state).toContainText('"choices": ["first"]');
    const slider = view.getByRole("slider");
    await slider.focus();
    await slider.press("ArrowRight");
    await expect(slider).toHaveAttribute("aria-valuenow", "25");
    await expect(state).toContainText('"range": [25]');
    await view.getByRole("combobox", { name: "Native select" }).click();
    await page.getByRole("option", { name: "Native second" }).click();
    await expect(state).toContainText('"native_select": "two"');
    await expect(view.getByRole("combobox", { name: "Native select" })).toHaveText("Native second");
    await view.getByRole("radio", { name: "Radio second" }).click();
    await expect(state).toContainText('"radio": "two"');
    await view.getByRole("tab", { name: "Details", exact: true }).click();
    await expect(view.getByRole("tabpanel")).toHaveText("Details panel");
    await view.getByRole("button", { name: "Open dialog", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Plugin dialog" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveCSS("border-top-color", "rgb(13, 148, 136)");
    expect(
      await dialog.evaluate((node) =>
        node.closest("[data-plugin-portal]")?.getAttribute("data-plugin-portal"),
      ),
    ).toBe("declarative-showcase/showcase");
    await dialog.getByRole("textbox").fill("Focused inside portal");
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
    await expect(view.getByRole("button", { name: "Open dialog", exact: true })).toBeFocused();
    await view.getByRole("button", { name: "Open menu", exact: true }).click();
    await expect(page.getByRole("menu")).toHaveCSS("border-top-color", "rgb(13, 148, 136)");
    await page.getByRole("menuitem", { name: "Menu action" }).click();
    await expect(state).toContainText('"menu": null');
    await view.getByRole("button", { name: "Open popover", exact: true }).click();
    await expect(page.getByText("Popover content", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Close popover", exact: true }).click();
    await view.getByRole("button", { name: "Radix tooltip trigger" }).hover();
    await expect(page.getByRole("tooltip", { name: "Radix tooltip content" })).toBeVisible();
    await page.mouse.move(0, 0, { steps: 5 });
    await expect(page.getByRole("tooltip", { name: "Radix tooltip content" })).not.toBeVisible();
    const projectTooltipTrigger = view.getByRole("button", { name: "Project tooltip trigger" });
    await projectTooltipTrigger.scrollIntoViewIfNeeded();
    await projectTooltipTrigger.hover();
    await expect(page.getByRole("tooltip", { name: "Project tooltip content" })).toBeVisible();
    await page.mouse.move(0, 0, { steps: 5 });
    // A malicious global-looking selector is constrained by @scope; fonts/imports never load.
    const bodyColor = await page.locator("body").evaluate((el) => getComputedStyle(el).color);
    await page.evaluate(() => {
      const sentinel = document.createElement("button");
      sentinel.id = "host-css-sentinel";
      sentinel.textContent = "Host sentinel";
      document.body.appendChild(sentinel);
    });
    await page.route("**/plugins/declarative-showcase/views/showcase/render", async (route) => {
      const response = await route.fetch();
      const data = await response.json();
      data.css += ".deep {".repeat(40) + "color:red;" + "}".repeat(40);
      data.css +=
        ' body, button { color: rgb(1, 2, 3) !important; } @font-face {font-family: bad; src:url(https://invalid.example/font)} @property --bad {syntax:"*";inherits:true} .showcase-title {background-image:url(javascript:alert(1))}';
      await route.fulfill({ response, json: data });
    });
    await page.evaluate(() =>
      window.dispatchEvent(
        new CustomEvent("openfic:plugin-event", { detail: { event: "ui.invalidate", data: {} } }),
      ),
    );
    await expect(view.getByRole("button", { name: "Open dialog", exact: true })).toHaveCSS(
      "color",
      "rgb(1, 2, 3)",
    );
    expect(await page.locator("body").evaluate((el) => getComputedStyle(el).color)).toBe(bodyColor);
    await expect(page.locator("#host-css-sentinel")).not.toHaveCSS("color", "rgb(1, 2, 3)");
    await expect(view).toContainText("Plugin stylesheet exceeds the depth/rule budget.");
    expect(await view.locator(":scope > style").textContent()).not.toContain("@font-face");
    expect(await view.locator(":scope > style").textContent()).not.toContain("javascript:");
    const animation = await view
      .locator(".showcase-animated")
      .evaluate((el) => getComputedStyle(el).animationName);
    expect(animation).toMatch(/^plugin-ui-.*-showcase-pulse$/);
    expect(animation).not.toBe(statusAnimation);
    await expect(status).toHaveCSS("color", "rgb(14, 116, 144)");
    await page.unroute("**/plugins/declarative-showcase/views/showcase/render");
    await page.reload();
    await expect(view.getByTestId("state")).toContainText(modelId);
    expect(errors).toEqual([]);
  } finally {
    await page.request.delete(api + "/plugins/" + plugin);
    if (projectId) await page.request.delete(api + "/projects/" + projectId);
    if (modelId) await page.request.delete(api + "/models/" + modelId);
    if (providerId) await page.request.delete(api + "/model-providers/" + providerId);
  }
});

test("project selectors keep their mobile sheets and portal focus", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await install(page);
  let projectId = "";
  try {
    const project = await page.request.post(api + "/projects", {
      multipart: { title: "Mobile UI Project" },
    });
    expect(project.ok()).toBeTruthy();
    projectId = (await project.json()).id;
    await page.goto("/extensions/" + plugin + "/showcase");
    const view = page.locator('[data-plugin-view="declarative-showcase/showcase"]');
    await view.locator('[data-plugin-component="ProjectSelectField"]').getByRole("textbox").click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible();
    await sheet.getByRole("button", { name: /Mobile UI Project/ }).click();
    await expect(view.getByTestId("state")).toContainText(projectId);
    await expect(sheet).not.toBeVisible();
  } finally {
    await page.request.delete(api + "/plugins/" + plugin);
    if (projectId) await page.request.delete(api + "/projects/" + projectId);
  }
});
