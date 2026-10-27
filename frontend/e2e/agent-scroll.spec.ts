import { expect, test, type Page } from "@playwright/test";

async function openFixture(page: Page, invalid = false) {
  await page.route("**/__agent_scroll_fixture*", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: `<div id="root"></div>
<script type="module">
import RefreshRuntime from "/@react-refresh";
RefreshRuntime.injectIntoGlobalHook(window);
window.$RefreshReg$ = () => {};
window.$RefreshSig$ = () => type => type;
window.__vite_plugin_react_preamble_installed__ = true;
</script><script type="module" src="/e2e/agent-scroll.fixture.tsx"></script>`,
    }),
  );
  await page.route("**/api/v1/**", (route) => route.fulfill({ status: 400, json: {} }));
  await page.goto(`/__agent_scroll_fixture${invalid ? "?invalid" : ""}`);
  await expect(page.locator(".agent-tool-card")).toBeVisible();
  await expect.poll(() => distanceFromBottom(page)).toBeLessThanOrEqual(2);
}

async function distanceFromBottom(page: Page) {
  return page
    .locator(".ai-sidebar-messages")
    .evaluate((element) => element.scrollHeight - element.scrollTop - element.clientHeight);
}

async function scrollUp(page: Page) {
  await page.locator(".ai-sidebar-messages").hover();
  await page.mouse.wheel(0, -500);
  await expect(page.getByTestId("at-bottom")).toHaveText("false");
  await expect.poll(() => distanceFromBottom(page)).toBeGreaterThan(400);
}

test("sending after scrolling up resumes following the streamed reply", async ({ page }) => {
  await openFixture(page);
  await scrollUp(page);
  await page.getByRole("button", { name: "发送" }).click();
  await expect(page.getByText("回答第 29 行")).toBeVisible();
  await expect.poll(() => distanceFromBottom(page)).toBeLessThanOrEqual(2);
  await expect(page.getByTestId("at-bottom")).toHaveText("true");
});

test("a rejected send does not reset the scroll position", async ({ page }) => {
  await openFixture(page, true);
  await scrollUp(page);
  const distance = await distanceFromBottom(page);
  await page.getByRole("button", { name: "发送" }).click();
  await expect(page.getByTestId("at-bottom")).toHaveText("false");
  expect(Math.abs((await distanceFromBottom(page)) - distance)).toBeLessThanOrEqual(2);
});

test("the final tool expansion remains anchored after the agent stops", async ({ page }) => {
  await openFixture(page);
  await page.getByRole("button", { name: "完成工具并结束" }).click();
  await expect(page.locator(".agent-chapter-diff-card")).toBeVisible();
  await page.waitForTimeout(500);
  await expect.poll(() => distanceFromBottom(page)).toBeLessThanOrEqual(2);
  await expect(page.getByTestId("at-bottom")).toHaveText("true");
});

test("a user scroll prevents following the final tool expansion", async ({ page }) => {
  await openFixture(page);
  await scrollUp(page);
  await page.getByRole("button", { name: "完成工具并结束" }).click();
  await expect(page.locator(".agent-chapter-diff-card")).toBeVisible();
  await page.waitForTimeout(500);
  await expect(page.getByTestId("at-bottom")).toHaveText("false");
  await expect.poll(() => distanceFromBottom(page)).toBeGreaterThan(400);
});
