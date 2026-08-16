import { expect, test } from "@playwright/test";

import {
  EMPTY_PROJECT_URL,
  SEND_BUTTON,
  approveUntilReply,
  openProject,
  sendMessage,
  startNewTask,
  typeMessage,
  waitForRunningState,
} from "./helpers";

test.describe("消息排队", () => {
  test("运行中发送新消息进入排队并在首条完成后继续", async ({ page }) => {
    await openProject(page, EMPTY_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(
      page,
      `请分三步执行：第一步，创建一个名为「排队测试${Date.now().toString(36)}」的章节。第二步，写入 50 字内容。第三步，完成前不要提前回复总结。`,
    );
    await waitForRunningState(page);

    await typeMessage(page, "第一条完成后请回复「第二条已处理」，不要执行其他工具。");

    const messageResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().includes("/agent/sessions/") &&
        response.url().endsWith("/message"),
      { timeout: 30000 },
    );
    await page.locator(SEND_BUTTON).click();
    const response = await messageResponse;
    expect(response.status()).toBe(200);
    const body = (await response.json()) as { queued?: boolean };
    expect(body.queued).toBe(true);

    await approveUntilReply(page, "第二条已处理", 480000);
  });
});
