import { expect, test } from "@playwright/test";

import {
  APPROVAL_PANEL,
  EMPTY_PROJECT_ID,
  EMPTY_PROJECT_URL,
  SEND_BUTTON,
  approveUntilReply,
  cancelSessionViaApi,
  getLatestTask,
  getLatestTaskDetail,
  getSessionState,
  getSettingsLock,
  openProject,
  sendMessage,
  startNewTask,
  waitForApprovalPanel,
  waitForAssistantReply,
  waitForRunningState,
  waitForTaskRunning,
} from "./helpers";

test.describe("审批恢复与取消互斥", () => {
  test("审批执行后会话继续直至完成", async ({ page }) => {
    await openProject(page, EMPTY_PROJECT_URL);
    await startNewTask(page);

    const chapterName = `审批测试${Date.now().toString(36)}`;
    await sendMessage(
      page,
      `请分两步执行：第一步，创建一个名为「${chapterName}」的章节。第二步，写入 50 字内容。完成后回复「审批完成」。`,
    );
    await waitForApprovalPanel(page);

    await approveUntilReply(page, "审批完成");
  });

  test("取消后审批恢复被拒绝且锁与状态正确", async ({ page }) => {
    await openProject(page, EMPTY_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(
      page,
      `请分两步执行：第一步，创建一个名为「取消审批${Date.now().toString(36)}」的章节。第二步，写入 50 字内容。完成后回复「完成」。`,
    );
    await waitForApprovalPanel(page);

    const task = await getLatestTaskDetail(page, EMPTY_PROJECT_ID);
    expect(task.agent_session_id).toBeTruthy();
    const sessionId = task.agent_session_id as string;

    const runningTask = await getLatestTask(page, EMPTY_PROJECT_ID);
    expect(runningTask.is_running).toBe(true);

    const cancelStatus = await cancelSessionViaApi(page, sessionId);
    expect(cancelStatus).toBe(200);

    await expect(getSettingsLock(page)).resolves.toBe(false);

    const state = await getSessionState(page, sessionId);
    expect(state.interrupts ?? []).toHaveLength(0);

    const cancelledTask = await getLatestTask(page, EMPTY_PROJECT_ID);
    expect(cancelledTask.is_running).toBe(false);

    await page.locator(APPROVAL_PANEL).getByRole("button", { name: "执行" }).click();

    await expect(page.getByText("工具审批失败").first()).toBeVisible({ timeout: 30000 });
  });

  test("运行中取消后旧任务不被新消息复活", async ({ page }) => {
    await openProject(page, EMPTY_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(
      page,
      `请分两步执行：第一步，创建一个名为「复活测试${Date.now().toString(36)}」的章节。第二步，写入 50 字内容。完成后回复「完成」。`,
    );
    await waitForRunningState(page);
    await waitForTaskRunning(page, EMPTY_PROJECT_ID);

    const oldTask = await getLatestTaskDetail(page, EMPTY_PROJECT_ID);
    expect(oldTask.agent_session_id).toBeTruthy();
    const oldSessionId = oldTask.agent_session_id as string;
    const oldRevisionId = oldTask.current_revision_id;

    await page.locator(SEND_BUTTON).click();
    await expect(page.getByText("正在考虑下一步").first()).toBeHidden({ timeout: 60000 });

    const cancelledTask = await getLatestTask(page, EMPTY_PROJECT_ID);
    expect(cancelledTask.is_running).toBe(false);
    const cancelledState = await getSessionState(page, oldSessionId);
    expect(cancelledState.interrupts ?? []).toHaveLength(0);

    await sendMessage(page, "回复「新会话正常」五个字，不要执行任何工具。");
    await waitForAssistantReply(page, "新会话正常");

    const finalTask = await getLatestTaskDetail(page, EMPTY_PROJECT_ID);
    expect(finalTask.agent_session_id).toBe(oldSessionId);
    expect(finalTask.is_running).toBe(false);
    expect(finalTask.current_revision_id).toBeTruthy();
    expect(finalTask.current_revision_id).not.toBe(oldRevisionId);
  });
});
