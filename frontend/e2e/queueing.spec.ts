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

test.describe("Antrean pesan", () => {
  test("pesan baru yang dikirim saat berjalan masuk antrean dan berlanjut setelah pesan pertama selesai", async ({ page }) => {
    await openProject(page, EMPTY_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(
      page,
      `Kerjakan dalam tiga langkah: pertama, buat sebuah bab bernama 'Uji antrean${Date.now().toString(36)}'. Kedua, tulis 50 kata isi. Ketiga, jangan membalas ringkasan lebih awal sebelum selesai.`,
    );
    await waitForRunningState(page);

    await typeMessage(page, "Setelah pesan pertama selesai, balas dengan 'Pesan kedua telah diproses', jangan jalankan alat lain.");

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

    await approveUntilReply(page, "Pesan kedua telah diproses", 480000);
  });
});
