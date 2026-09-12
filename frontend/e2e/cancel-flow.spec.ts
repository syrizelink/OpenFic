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

test.describe("Alur pembatalan sesi", () => {
  test("sesi berhenti setelah dibatalkan saat berjalan dan dapat dimulai ulang", async ({ page }) => {
    await openProject(page, EMPTY_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(
      page,
      `Kerjakan dalam dua langkah: pertama, buat sebuah bab bernama 'Uji pembatalan${Date.now().toString(36)}'. Kedua, tulis 60 kata isi pada bab tersebut. Setelah selesai, balas dengan 'Selesai'.`,
    );
    await waitForRunningState(page);
    await waitForTaskRunning(page, EMPTY_PROJECT_ID);

    const stopButton = page.locator(SEND_BUTTON);
    await expect(stopButton).toBeEnabled();
    await stopButton.click();

    await expect(page.getByText("Mempertimbangkan langkah berikutnya").first()).toBeHidden({ timeout: 60000 });

    await expect(async () => {
      const runningTexts = await page.getByText(/Mempertimbangkan langkah berikutnya|Menunggu persetujuan|Menjalankan tugas/).count();
      expect(runningTexts).toBe(0);
    }).toPass({ timeout: 30000 });

    await sendMessage(page, "Balas dengan kalimat 'Sesi normal' saja, jangan jalankan alat apa pun.");
    await waitForRunningState(page);
    await waitForAssistantReply(page, "Sesi normal");
  });
});
