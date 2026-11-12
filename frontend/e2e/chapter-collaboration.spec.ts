import { expect, test } from "@playwright/test";

test("two chapter editors sync, preserve cursor and local undo, and keep editing while Agent runs", async ({
  context,
  request,
}) => {
  await context.grantPermissions(["local-network-access"]);
  const api = "http://127.0.0.1:8000/api/v1";
  const projectResponse = await request.post(`${api}/projects`, {
    multipart: { title: "Collaboration e2e" },
  });
  expect(projectResponse.ok()).toBeTruthy();
  const project = await projectResponse.json();
  const tree = await (await request.get(`${api}/projects/${project.id}/chapters`)).json();
  const chapter = await (
    await request.post(`${api}/projects/${project.id}/chapters`, {
      data: {
        volume_id: tree.volumes[0].id,
        title: "Shared chapter",
        content: "Sunny morning\nThe end",
      },
    })
  ).json();
  const enabled = await request.patch(`${api}/settings`, {
    data: { human_ai_collaboration: true },
  });
  expect(enabled.ok()).toBeTruthy();
  await context.route("**/__chapter_collaboration_fixture?*", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: `<div id="root"></div><script type="module">
import RefreshRuntime from "/@react-refresh";
RefreshRuntime.injectIntoGlobalHook(window);
window.$RefreshReg$ = () => {};
window.$RefreshSig$ = () => type => type;
window.__vite_plugin_react_preamble_installed__ = true;
</script><script type="module" src="/e2e/chapter-collaboration.fixture.tsx"></script>`,
    }),
  );
  const first = await context.newPage(),
    second = await context.newPage();
  const errors: string[] = [];
  first.on("pageerror", (e) => errors.push(e.message));
  second.on("pageerror", (e) => errors.push(e.message));
  try {
    await first.goto(`/__chapter_collaboration_fixture?chapter=${chapter.id}`);
    await second.goto(`/__chapter_collaboration_fixture?chapter=${chapter.id}`);
    const left = first.locator(".chapter-editor-content .ProseMirror");
    const right = second.locator(".chapter-editor-content .ProseMirror");
    await expect(left).toContainText("Sunny morning");
    await expect(right).toContainText("Sunny morning");
    await first.getByRole("button", { name: "Toggle Agent running" }).click();
    await expect(left).toHaveAttribute("contenteditable", "true");
    await left.click();
    await first.keyboard.press("Control+End");
    await first.keyboard.insertText(" and bells");
    await right.click();
    await second.keyboard.press("Control+Home");
    await second.keyboard.insertText("Rain instead. ");
    await expect(left).toContainText("Rain instead. Sunny morning");
    await expect(right).toContainText("The end and bells");
    await first.keyboard.insertText(" ring");
    await expect(left).toContainText("The end and bells ring");
    await expect
      .poll(async () => (await (await request.get(`${api}/chapters/${chapter.id}`)).json()).content)
      .toBe("Rain instead. Sunny morning\nThe end and bells ring");
    await second.keyboard.press("Control+z");
    await expect(left).not.toContainText("Rain instead.");
    await expect(left).toContainText("and bells ring");
    await expect
      .poll(async () => (await (await request.get(`${api}/chapters/${chapter.id}`)).json()).content)
      .toBe("Sunny morning\nThe end and bells ring");
    await first.reload();
    await expect(first.locator(".ProseMirror")).toContainText("and bells ring");
    // Pending CRDT edits survive an offline interval and converge on reconnect.
    await context.setOffline(true);
    const reloaded = first.locator(".chapter-editor-content .ProseMirror");
    await reloaded.click();
    await first.keyboard.press("Control+End");
    await first.keyboard.insertText(" offline");
    await context.setOffline(false);
    await expect(right).toContainText("and bells ring offline");
    await expect
      .poll(async () => (await (await request.get(`${api}/chapters/${chapter.id}`)).json()).content)
      .toBe("Sunny morning\nThe end and bells ring offline");
    await first.getByRole("button", { name: "Toggle Agent running" }).click();
    await request.patch(`${api}/settings`, { data: { human_ai_collaboration: false } });
    await expect(reloaded).toHaveAttribute("contenteditable", "false");
    await expect(reloaded).toContainText("and bells ring offline");
    expect(errors).toEqual([]);
    await first.screenshot({ path: "/tmp/openfic-collaboration.png", fullPage: true });
  } finally {
    await first.close();
    await second.close();
    await request.patch(`${api}/settings`, { data: { human_ai_collaboration: false } });
    await request.delete(`${api}/projects/${project.id}`);
  }
});
