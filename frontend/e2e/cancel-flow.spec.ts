import { expect, test } from "@playwright/test";

import {
  EMPTY_PROJECT_ID,
  EMPTY_PROJECT_URL,
  SEND_BUTTON,
  openProject,
  sendMessage,
  startNewTask,
  waitForAssistantReply,
  waitForRunningState,
  waitForTaskRunning,
} from "./helpers";

test.describe("会话取消流程", () => {
  test("运行中取消后会话停止并可重新开始", async ({ page }) => {
    await openProject(page, EMPTY_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(
      page,
      `请分两步执行：第一步，创建一个名为「取消测试${Date.now().toString(36)}」的章节。第二步，在该章节中写入 60 字内容。完成后回复「完成」。`,
    );
    await waitForRunningState(page);
    await waitForTaskRunning(page, EMPTY_PROJECT_ID);

    const stopButton = page.locator(SEND_BUTTON);
    await expect(stopButton).toBeEnabled();
    await stopButton.click();

    await expect(page.getByText("正在考虑下一步").first()).toBeHidden({ timeout: 60000 });

    await expect(async () => {
      const runningTexts = await page.getByText(/正在考虑下一步|正在等待审批|正在执行/).count();
      expect(runningTexts).toBe(0);
    }).toPass({ timeout: 30000 });

    await sendMessage(page, "回复「会话正常」四个字，不要执行任何工具。");
    await waitForRunningState(page);
    await waitForAssistantReply(page, "会话正常");
  });
});
