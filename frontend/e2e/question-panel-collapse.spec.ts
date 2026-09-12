import { expect, test } from "@playwright/test";

import { EMPTY_PROJECT_URL, openProject, sendMessage, startNewTask } from "./helpers";

const QUESTION_PANEL = ".agent-special-panel-question";

test.describe("Penciutan panel pertanyaan", () => {
  test("panel pertanyaan dapat diciutkan menjadi ringkasan dan dibentangkan kembali", async ({ page }) => {
    await openProject(page, EMPTY_PROJECT_URL);
    await startNewTask(page);

    await sendMessage(
      page,
      "Gunakan alat ask_user untuk mengajukan satu pertanyaan klarifikasi kepada saya tentang preferensi penulisan, lalu berhenti sebelum saya menjawab, jangan jalankan alat lain.",
    );

    const panel = page.locator(QUESTION_PANEL);
    await expect(panel).toBeVisible({ timeout: 180000 });
    await expect(panel.getByRole("button", { name: "Ciutkan panel pertanyaan" })).toBeVisible();
    await expect(panel.locator(".agent-special-panel-content")).toBeVisible();

    await panel.getByRole("button", { name: "Ciutkan panel pertanyaan" }).click();

    await expect(panel.locator(".agent-special-panel-content")).toBeHidden();
    await expect(panel.getByRole("button", { name: "Bentangkan panel pertanyaan" })).toBeVisible();
    await expect(panel).toContainText("Perlu informasi tambahan");

    await panel.getByRole("button", { name: "Bentangkan panel pertanyaan" }).click();

    await expect(panel.locator(".agent-special-panel-content")).toBeVisible();
    await expect(panel.getByRole("button", { name: "Ciutkan panel pertanyaan" })).toBeVisible();
  });
});
