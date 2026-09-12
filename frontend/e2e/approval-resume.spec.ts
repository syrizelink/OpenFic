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

test.describe("Pemulihan persetujuan dan saling eksklusif dengan pembatalan", () => {
  test("sesi berlanjut sampai selesai setelah persetujuan dijalankan", async ({ page }) => {
    await openProject(page, EMPTY_PROJECT_URL);
    await startNewTask(page);

    const chapterName = `Uji persetujuan${Date.now().toString(36)}`;
    await sendMessage(
      page,
      `Kerjakan dalam dua langkah: pertama, buat sebuah bab bernama '${chapterName}'. Kedua, tulis 50 kata isi. Setelah selesai, balas dengan 'Persetujuan selesai'.`,
    );
    await waitForApprovalPanel(page);

    await approveUntilReply(page, "Persetujuan selesai");
  });

  test("pemulihan persetujuan ditolak setelah pembatalan serta kunci dan status tetap benar", async ({ page }) => {
    await openProject(page, EMPTY_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(
      page,
      `Kerjakan dalam dua langkah: pertama, buat sebuah bab bernama 'Batalkan persetujuan${Date.now().toString(36)}'. Kedua, tulis 50 kata isi. Setelah selesai, balas dengan 'Selesai'.`,
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

    await page.locator(APPROVAL_PANEL).getByRole("button", { name: "Jalankan" }).click();

    await expect(page.getByText("Persetujuan alat gagal").first()).toBeVisible({ timeout: 30000 });
  });

  test("tugas lama tidak dihidupkan kembali oleh pesan baru setelah dibatalkan saat berjalan", async ({ page }) => {
    await openProject(page, EMPTY_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(
      page,
      `Kerjakan dalam dua langkah: pertama, buat sebuah bab bernama 'Uji hidup kembali${Date.now().toString(36)}'. Kedua, tulis 50 kata isi. Setelah selesai, balas dengan 'Selesai'.`,
    );
    await waitForRunningState(page);
    await waitForTaskRunning(page, EMPTY_PROJECT_ID);

    const oldTask = await getLatestTaskDetail(page, EMPTY_PROJECT_ID);
    expect(oldTask.agent_session_id).toBeTruthy();
    const oldSessionId = oldTask.agent_session_id as string;
    const oldRevisionId = oldTask.current_revision_id;

    await page.locator(SEND_BUTTON).click();
    await expect(page.getByText("Mempertimbangkan langkah berikutnya").first()).toBeHidden({ timeout: 60000 });

    const cancelledTask = await getLatestTask(page, EMPTY_PROJECT_ID);
    expect(cancelledTask.is_running).toBe(false);
    const cancelledState = await getSessionState(page, oldSessionId);
    expect(cancelledState.interrupts ?? []).toHaveLength(0);

    await sendMessage(page, "Balas dengan kalimat 'Sesi baru normal' saja, jangan jalankan alat apa pun.");
    await waitForAssistantReply(page, "Sesi baru normal");

    const finalTask = await getLatestTaskDetail(page, EMPTY_PROJECT_ID);
    expect(finalTask.agent_session_id).toBe(oldSessionId);
    expect(finalTask.is_running).toBe(false);
    expect(finalTask.current_revision_id).toBeTruthy();
    expect(finalTask.current_revision_id).not.toBe(oldRevisionId);
  });
});
