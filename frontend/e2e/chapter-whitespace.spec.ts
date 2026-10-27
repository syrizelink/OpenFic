import { expect, test } from "@playwright/test";

test("chapter whitespace survives saving, switching chapters, and a remote refresh", async ({
  page,
}) => {
  const chapters: Record<string, { content: string; updated_at: string }> = {
    first: { content: "", updated_at: "2026-01-01T00:00:00Z" },
    second: { content: "other", updated_at: "2026-01-01T00:00:00Z" },
  };
  await page.route("**/__chapter_whitespace_fixture", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: `<div id="root"></div><script type="module">
import RefreshRuntime from "/@react-refresh";
RefreshRuntime.injectIntoGlobalHook(window);
window.$RefreshReg$ = () => {};
window.$RefreshSig$ = () => type => type;
window.__vite_plugin_react_preamble_installed__ = true;
</script><script type="module" src="/e2e/chapter-whitespace.fixture.tsx"></script>`,
    }),
  );
  await page.route("**/api/v1/settings", (route) =>
    route.fulfill({ json: { editor_auto_indent: false } }),
  );
  await page.route("**/api/v1/chapters/*", async (route) => {
    const id = new URL(route.request().url()).pathname.split("/").pop()!;
    if (route.request().method() === "PATCH") {
      const data = route.request().postDataJSON() as { content: string };
      chapters[id].content = data.content;
      chapters[id].updated_at = "2026-01-02T00:00:00Z";
    }
    await route.fulfill({
      json: {
        id,
        project_id: "project",
        volume_id: "volume",
        title: id,
        word_count: 0,
        order: 0,
        created_at: "2026-01-01T00:00:00Z",
        ...chapters[id],
      },
    });
  });

  await page.goto("/__chapter_whitespace_fixture");
  const editor = page.locator(".chapter-editor-content .ProseMirror");
  await editor.click();
  await page.keyboard.press("Enter");
  await page.keyboard.insertText("　　第一段");
  await page.keyboard.press("Enter");
  await page.keyboard.insertText("  第二段  ");
  await page.keyboard.press("Enter");
  await page.keyboard.insertText("　　");
  await page.keyboard.press("Enter");
  await page.keyboard.press("Control+s");
  const expected = "\n　　第一段\n  第二段  \n　　\n";
  await expect.poll(() => chapters.first.content).toBe(expected);
  await page.getByRole("button", { name: "Second chapter" }).click();
  await expect(editor).toContainText("other");
  await page.getByRole("button", { name: "First chapter" }).click();
  await expect
    .poll(() => editor.locator("p").allTextContents())
    .toEqual(["", "　　第一段", "  第二段  ", "　　", ""]);

  chapters.first.content = "  更新的首行\n　　下一行  ";
  chapters.first.updated_at = "2026-01-03T00:00:00Z";
  await page.getByRole("button", { name: "Refresh chapter" }).click();
  await expect
    .poll(() => editor.locator("p").allTextContents())
    .toEqual(["  更新的首行", "　　下一行  "]);
});
