import { expect, test, type Page } from "@playwright/test";

async function openForm(page: Page, initial = "") {
  await page.route("**/__model_dimensions_fixture*", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: `<div id="root"></div>
<script type="module">
import RefreshRuntime from "/@react-refresh";
RefreshRuntime.injectIntoGlobalHook(window);
window.$RefreshReg$ = () => {};
window.$RefreshSig$ = () => type => type;
window.__vite_plugin_react_preamble_installed__ = true;
</script><script type="module" src="/e2e/model-dimensions.fixture.tsx"></script>`,
    }),
  );
  await page.route("**/api/v1/model-providers", (route) =>
    route.fulfill({
      json: [
        {
          id: "provider",
          name: "Cohere",
          url: "https://embedding.test/v1",
          provider_type: "cohere",
          supported_task_types: ["embedding"],
          is_builtin: false,
          created_at: "",
          updated_at: "",
        },
      ],
    }),
  );
  await page.route("**/api/v1/model-provider-catalog/**", (route) =>
    route.fulfill({
      json: {
        provider: {
          provider_type: "cohere",
          display_name: "Cohere",
          supported_task_types: ["embedding"],
          model_counts: {},
        },
        task_type: "embedding",
        models: [],
      },
    }),
  );
  await page.goto(`/__model_dimensions_fixture?initial=${initial}`);
  await expect(page.getByRole("button", { name: "自动获取", exact: true })).toBeEnabled();
}

test("fetched dimensions fill the field and save in the existing dimensions field", async ({
  page,
}) => {
  await page.route("**/api/v1/models/embedding-dimensions", (route) => {
    expect(route.request().postDataJSON()).toEqual({
      provider_id: "provider",
      model_id: "embedding-model",
    });
    return route.fulfill({ json: { dimensions: 6144 } });
  });
  await openForm(page);
  await page.getByRole("button", { name: "自动获取", exact: true }).click();
  await expect(page.getByRole("spinbutton")).toHaveValue("6144");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByTestId("submitted")).toContainText('"dimensions":6144');
});

test("fetched dimensions remain editable", async ({ page }) => {
  await openForm(page, "filled");
  await expect(page.getByRole("spinbutton")).toHaveValue("6144");
  await page.getByRole("spinbutton").fill("2048");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByTestId("submitted")).toContainText('"dimensions":2048');
});

test("late responses do not fill dimensions for a different model", async ({ page }) => {
  let finish: (() => void) | undefined;
  const pending = new Promise<void>((resolve) => {
    finish = resolve;
  });
  await page.route("**/api/v1/models/embedding-dimensions", async (route) => {
    await pending;
    await route.fulfill({ json: { dimensions: 6144 } });
  });
  await openForm(page);
  await page.getByRole("button", { name: "自动获取", exact: true }).click();
  await expect(page.getByRole("button", { name: "保存", exact: true })).toBeDisabled();
  await page
    .getByRole("dialog")
    .getByPlaceholder("输入模型 ID（如 gpt-4, claude-3-opus）")
    .fill("another-model");
  const response = page.waitForResponse("**/api/v1/models/embedding-dimensions");
  finish!();
  await (await response).finished();
  await page.evaluate(() => new Promise(requestAnimationFrame));
  await expect(page.getByRole("spinbutton")).toHaveValue("");
});

test("failed detection keeps an existing manual dimension", async ({ page }) => {
  await page.route("**/api/v1/models/embedding-dimensions", (route) =>
    route.fulfill({
      status: 400,
      json: { detail: "自动获取维度失败：模型不可用" },
    }),
  );
  await openForm(page, "manual");
  await expect(page.getByRole("spinbutton")).toHaveValue("1536");
  await page.getByRole("button", { name: "自动获取", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("模型不可用");
  await expect(page.getByRole("spinbutton")).toHaveValue("1536");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByTestId("submitted")).toContainText('"dimensions":1536');
});
