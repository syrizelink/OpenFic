import { expect, test } from "@playwright/test";

import {
  COMPACT_BUTTON,
  LARGE_PROJECT_ID,
  LARGE_PROJECT_URL,
  approveUntilReply,
  cancelSessionViaApi,
  getLatestTaskDetail,
  openProject,
  sendMessage,
  startNewTask,
  waitForAssistantReply,
} from "./helpers";

const READ_TASK =
  "请连续使用读章节工具，读取第一卷的前 15 章内容，不要概括内容。全部读完后回复「阅读完成」。不要修改任何章节。";

const SECOND_TURN =
  "请用一句话总结你刚才读到的五章内容的整体基调，回复以「总结完成」结尾。不要执行任何工具。";

test.describe("上下文压缩", () => {
  test("大项目多轮会话后手动压缩成功", async ({ page }) => {
    await openProject(page, LARGE_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(page, READ_TASK);
    await approveUntilReply(page, "阅读完成", 600000);

    await sendMessage(page, SECOND_TURN);
    await waitForAssistantReply(page, "总结完成", 300000);

    await expect(page.getByRole("button", { name: COMPACT_BUTTON })).toBeEnabled({
      timeout: 60000,
    });

    await page.getByRole("button", { name: COMPACT_BUTTON }).click();

    await expect(page.getByText("上下文已压缩").first()).toBeVisible({ timeout: 600000 });
    await expect(page.getByRole("button", { name: COMPACT_BUTTON })).toBeEnabled({
      timeout: 60000,
    });
  });

  test("压缩期间取消会话", async ({ page }) => {
    await openProject(page, LARGE_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(page, READ_TASK);
    await approveUntilReply(page, "阅读完成", 600000);

    await sendMessage(page, SECOND_TURN);
    await waitForAssistantReply(page, "总结完成", 300000);

    await expect(page.getByRole("button", { name: COMPACT_BUTTON })).toBeEnabled({
      timeout: 60000,
    });

    const task = await getLatestTaskDetail(page, LARGE_PROJECT_ID);
    expect(task.agent_session_id).toBeTruthy();

    await page.getByRole("button", { name: COMPACT_BUTTON }).click();
    await expect(page.getByText("正在压缩上下文").first()).toBeVisible({ timeout: 60000 });

    await page.waitForTimeout(3000);

    const cancelStatus = await cancelSessionViaApi(page, task.agent_session_id as string);
    expect(cancelStatus).toBe(200);

    await expect(page.getByRole("button", { name: COMPACT_BUTTON })).toBeEnabled({
      timeout: 120000,
    });

    await sendMessage(page, "回复「压缩后会话正常」六个字，不要执行任何工具。");
    await waitForAssistantReply(page, "压缩后会话正常");
  });
});
