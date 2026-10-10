import { test, expect } from "@playwright/test";

test("dashboard loads details on demand and switches statistics without errors", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const details: string[] = [];
  const options = {
    project_ids: [],
    model_providers: [],
    model_ids: [],
    categories: [],
    operations: [],
    statuses: [],
    project_options: [],
    model_options: [],
  };
  await page.route("**/__dashboard_fixture", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: `<div id="root"></div>
<script type="module">
import RefreshRuntime from "/@react-refresh";
RefreshRuntime.injectIntoGlobalHook(window);
window.$RefreshReg$ = () => {};
window.$RefreshSig$ = () => type => type;
window.__vite_plugin_react_preamble_installed__ = true;
</script><script type="module" src="/e2e/dashboard.fixture.tsx"></script>`,
    }),
  );
  await page.route("**/api/v1/settings", (route) =>
    route.fulfill({
      json: { language: "zh-CN", audit_persist_details: true, telemetry_enabled: false },
    }),
  );
  await page.route("**/api/v1/agent-definitions", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/dashboard/llm-api/records?*", (route) =>
    route.fulfill({
      json: {
        options,
        records: {
          total: 1,
          page: 1,
          page_size: 20,
          items: [
            {
              id: "large-record",
              created_at: "2026-09-01T00:00:00Z",
              project_id: "p",
              project_title: "Project",
              model_id: "model",
              category: "agent",
              operation: "writer",
              status: "success",
              tokens_input: 1,
              tokens_output: 1,
              tokens_total: 2,
              token_cache: 0,
              tool_calls_count: 1,
              has_request_messages: true,
              has_tool_references: true,
              has_output_details: true,
            },
          ],
        },
      },
    }),
  );
  await page.route("**/api/v1/dashboard/llm-api/records/large-record/details", (route) => {
    details.push(route.request().url());
    return route.fulfill({
      json: {
        id: "large-record",
        tool_references: JSON.stringify([
          { name: "edit_chapter", description: "Tool description" },
        ]),
        response_content: "Long output ".repeat(20000),
        response_tool_calls: JSON.stringify([
          { name: "edit_chapter", args: { content: "Large tool argument ".repeat(20000) } },
        ]),
        error_message: null,
      },
    });
  });
  await page.route(/\/api\/v1\/dashboard\/llm-api\/stats(?:\?|$)/, (route) =>
    route.fulfill({
      json: {
        options,
        summary: {
          calls_total: 12000,
          success_total: 12000,
          tokens_total: 24000,
          tokens_input_total: 12000,
          tokens_output_total: 12000,
          avg_latency_ms: 900,
          avg_first_token_ms: 100,
        },
        model_time_series: [
          {
            date: "2026-09-01",
            key: "model",
            label: "Model",
            calls: 12000,
            tokens_total: 24000,
            avg_latency_ms: 900,
          },
        ],
        by_model: [{ key: "model", label: "Model", calls: 12000, tokens_total: 24000 }],
        by_project: [{ key: "p", label: "Project", calls: 12000, tokens_total: 24000 }],
      },
    }),
  );
  await page.goto("/__dashboard_fixture");
  await expect(page.locator(".dashboard-record-table tbody tr")).toHaveCount(1);
  expect(details).toHaveLength(0);
  await page.getByRole("button", { name: "查看输出" }).click();
  await expect(page.locator(".dashboard-output-text")).toContainText("Long output");
  await expect(page.locator(".dashboard-output-tool-call-summary")).toHaveText("edit_chapter");
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await page.getByRole("button", { name: "查看携带的工具" }).click();
  await expect(page.locator(".dashboard-output-json")).toContainText("Tool description");
  expect(details).toHaveLength(1);
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await page.getByRole("button", { name: "Switch tab" }).click();
  await expect(page.locator('.dashboard-chart[data-ready="true"]')).toHaveCount(6);
  await page.getByRole("button", { name: "Switch tab" }).click();
  await expect(page.locator(".dashboard-record-table tbody tr")).toHaveCount(1);
  expect(errors).toEqual([]);
});
