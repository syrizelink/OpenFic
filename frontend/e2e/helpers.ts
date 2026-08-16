import { expect, type Page } from "@playwright/test";

export const EMPTY_PROJECT_ID = "EDzAi3teTeKimQH_VXoxB";
export const LARGE_PROJECT_ID = "sEhu5CzLC-GfoDjsM01yg";

export const EMPTY_PROJECT_URL = `/projects/${EMPTY_PROJECT_ID}`;
export const LARGE_PROJECT_URL = `/projects/${LARGE_PROJECT_ID}`;

export const COMPOSER = ".ai-sidebar-input-body[data-mode='composer']";
export const SEND_BUTTON = ".ai-sidebar-send-button";
export const APPROVAL_PANEL = ".agent-special-panel-approval";
export const COMPACT_BUTTON = "压缩上下文";
export const NEW_TASK_BUTTON = "新建任务";

export interface TaskInfo {
  id: string;
  is_running: boolean;
  title: string;
}

export interface TaskDetail extends TaskInfo {
  agent_session_id: string | null;
  current_revision_id: string | null;
}

export async function apiRequest<T>(
  page: Page,
  method: "GET" | "POST",
  url: string,
  body?: unknown,
): Promise<{ status: number; data: T | null }> {
  const response = await page.request.fetch(url, {
    method,
    data: body,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
  });
  let data: T | null = null;
  try {
    data = (await response.json()) as T;
  } catch {
    data = null;
  }
  return { status: response.status(), data };
}

export async function listTasks(page: Page, projectId: string): Promise<TaskInfo[]> {
  const { status, data } = await apiRequest<{ items: TaskInfo[] }>(
    page,
    "GET",
    `/api/v1/projects/${projectId}/tasks`,
  );
  expect(status).toBe(200);
  return data?.items ?? [];
}

export async function getLatestTask(page: Page, projectId: string): Promise<TaskInfo> {
  const tasks = await listTasks(page, projectId);
  const task = tasks[0];
  expect(task).toBeTruthy();
  return task;
}

export async function getLatestTaskDetail(page: Page, projectId: string): Promise<TaskDetail> {
  const task = await getLatestTask(page, projectId);
  const { status, data } = await apiRequest<TaskDetail>(page, "GET", `/api/v1/tasks/${task.id}`);
  expect(status).toBe(200);
  expect(data).toBeTruthy();
  return data as TaskDetail;
}

export async function getSettingsLock(page: Page): Promise<boolean> {
  const { status, data } = await apiRequest<{ is_locked: boolean }>(
    page,
    "GET",
    "/api/v1/settings/agent-session-lock",
  );
  expect(status).toBe(200);
  return data?.is_locked === true;
}

export async function cancelSessionViaApi(page: Page, sessionId: string): Promise<number> {
  const { status } = await apiRequest(
    page,
    "POST",
    `/api/v1/agent/sessions/${sessionId}/cancel`,
    {},
  );
  return status;
}

export async function getSessionState(
  page: Page,
  sessionId: string,
): Promise<{
  status: number;
  is_running?: boolean;
  interrupts?: unknown[];
}> {
  const { status, data } = await apiRequest<{
    is_running?: boolean;
    interrupts?: unknown[];
  }>(page, "GET", `/api/v1/agent/sessions/${sessionId}`);
  return { status, ...(data ?? {}) };
}

export async function openProject(page: Page, projectUrl: string): Promise<void> {
  await page.goto(projectUrl);
  await expect(page.locator(".ai-sidebar-input-area")).toBeVisible({ timeout: 30000 });
}

export async function startNewTask(page: Page): Promise<void> {
  const newTaskButton = page.getByRole("button", { name: NEW_TASK_BUTTON });
  if (await newTaskButton.isVisible().catch(() => false)) {
    await newTaskButton.click();
  }
  await expect(page.locator(".ai-sidebar-input-area")).toBeVisible();
}

export const MESSAGES_AREA = ".agent-message-scroll-content";

export async function typeMessage(page: Page, text: string): Promise<void> {
  const editor = page.locator(`${COMPOSER} p`).first();
  await editor.click();
  await editor.fill(text);
}

export async function sendMessage(page: Page, text: string): Promise<void> {
  await typeMessage(page, text);
  const sendButton = page.locator(SEND_BUTTON);
  await expect(sendButton).toBeEnabled({ timeout: 10000 });
  await sendButton.click();
  const confirmButton = page.getByRole("button", { name: "继续发送" });
  if (await confirmButton.isVisible({ timeout: 5000 }).catch(() => false)) {
    await confirmButton.click();
  }
  const editor = page.locator(`${COMPOSER} p`).first();
  await expect(editor).toBeEmpty({ timeout: 10000 });
}

export async function waitForRunningState(page: Page, timeout = 120000): Promise<void> {
  await expect(page.getByText("正在考虑下一步").first()).toBeVisible({ timeout });
}

export async function waitForTaskRunning(
  page: Page,
  projectId: string,
  timeout = 60000,
): Promise<void> {
  await expect(async () => {
    const tasks = await listTasks(page, projectId);
    expect(tasks[0]?.is_running).toBe(true);
  }).toPass({ timeout });
}

export async function waitForAssistantReply(
  page: Page,
  text: string,
  timeout = 240000,
): Promise<void> {
  await expect(
    page.locator(`${MESSAGES_AREA} [data-block-type="agent"]`).getByText(text).first(),
  ).toBeVisible({ timeout });
}

export async function waitForApprovalPanel(page: Page, timeout = 180000): Promise<void> {
  await expect(page.locator(APPROVAL_PANEL)).toBeVisible({ timeout });
}

export async function approveUntilReply(
  page: Page,
  text: string,
  timeoutMs = 420000,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const approval = page.locator(APPROVAL_PANEL);
    if (await approval.isVisible().catch(() => false)) {
      await approval.getByRole("button", { name: "执行" }).click();
      await expect(approval)
        .toBeHidden({ timeout: 120000 })
        .catch(() => undefined);
    }
    const reply = page
      .locator(`${MESSAGES_AREA} [data-block-type="agent"]`)
      .getByText(text)
      .first();
    if (await reply.isVisible().catch(() => false)) return;
    await page.waitForTimeout(2000);
  }
  throw new Error(`未在 ${timeoutMs}ms 内收到回复: ${text}`);
}

export async function waitForIdle(page: Page, timeout = 180000): Promise<void> {
  await expect(page.locator(SEND_BUTTON)).toHaveClass(/ai-sidebar-send-button/, { timeout });
  await expect(async () => {
    const running = await page.getByText(/正在考虑下一步|正在等待审批|正在执行/).count();
    expect(running).toBe(0);
  }).toPass({ timeout });
}
