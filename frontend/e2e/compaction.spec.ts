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
  "Gunakan alat baca bab secara berurutan untuk membaca isi 15 bab pertama pada volume pertama, jangan meringkas isinya. Setelah semuanya dibaca, balas dengan 'Selesai membaca'. Jangan ubah bab apa pun.";

const SECOND_TURN =
  "Rangkum dalam satu kalimat nada keseluruhan dari lima bab yang baru saja kamu baca, akhiri balasan dengan 'Ringkasan selesai'. Jangan jalankan alat apa pun.";

test.describe("Pemadatan konteks", () => {
  test("pemadatan manual berhasil setelah sesi berbilang putaran pada proyek besar", async ({ page }) => {
    await openProject(page, LARGE_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(page, READ_TASK);
    await approveUntilReply(page, "Selesai membaca", 600000);

    await sendMessage(page, SECOND_TURN);
    await waitForAssistantReply(page, "Ringkasan selesai", 300000);

    await expect(page.getByRole("button", { name: COMPACT_BUTTON })).toBeEnabled({
      timeout: 60000,
    });

    await page.getByRole("button", { name: COMPACT_BUTTON }).click();

    await expect(page.getByText("Konteks dipadatkan").first()).toBeVisible({ timeout: 600000 });
    await expect(page.getByRole("button", { name: COMPACT_BUTTON })).toBeEnabled({
      timeout: 60000,
    });
  });

  test("membatalkan sesi selama pemadatan", async ({ page }) => {
    await openProject(page, LARGE_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(page, READ_TASK);
    await approveUntilReply(page, "Selesai membaca", 600000);

    await sendMessage(page, SECOND_TURN);
    await waitForAssistantReply(page, "Ringkasan selesai", 300000);

    await expect(page.getByRole("button", { name: COMPACT_BUTTON })).toBeEnabled({
      timeout: 60000,
    });

    const task = await getLatestTaskDetail(page, LARGE_PROJECT_ID);
    expect(task.agent_session_id).toBeTruthy();

    await page.getByRole("button", { name: COMPACT_BUTTON }).click();
    await expect(page.getByText("Memadatkan konteks").first()).toBeVisible({ timeout: 60000 });

    await page.waitForTimeout(3000);

    const cancelStatus = await cancelSessionViaApi(page, task.agent_session_id as string);
    expect(cancelStatus).toBe(200);

    await expect(page.getByRole("button", { name: COMPACT_BUTTON })).toBeEnabled({
      timeout: 120000,
    });

    await sendMessage(page, "Balas dengan kalimat 'Sesi normal setelah pemadatan' saja, jangan jalankan alat apa pun.");
    await waitForAssistantReply(page, "Sesi normal setelah pemadatan");
  });
});
