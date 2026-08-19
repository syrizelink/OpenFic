import { expect, test } from "@playwright/test";

import { EMPTY_PROJECT_URL, openProject, sendMessage, startNewTask } from "./helpers";

const QUESTION_PANEL = ".agent-special-panel-question";

test.describe("提问面板收起", () => {
  test("提问面板可以收起为摘要并重新展开", async ({ page }) => {
    await openProject(page, EMPTY_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(
      page,
      "请使用 ask_user 工具向我提出一个关于写作偏好的澄清问题，并在我回答前停止，不要执行其他工具。",
    );

    const panel = page.locator(QUESTION_PANEL);
    await expect(panel).toBeVisible({ timeout: 180000 });
    await expect(panel.getByRole("button", { name: "收起提问面板" })).toBeVisible();
    await expect(panel.locator(".agent-special-panel-content")).toBeVisible();

    await panel.getByRole("button", { name: "收起提问面板" }).click();

    await expect(panel.locator(".agent-special-panel-content")).toBeHidden();
    await expect(panel.getByRole("button", { name: "展开提问面板" })).toBeVisible();
    await expect(panel).toContainText("需要补充信息");

    await panel.getByRole("button", { name: "展开提问面板" }).click();

    await expect(panel.locator(".agent-special-panel-content")).toBeVisible();
    await expect(panel.getByRole("button", { name: "收起提问面板" })).toBeVisible();
  });
});
