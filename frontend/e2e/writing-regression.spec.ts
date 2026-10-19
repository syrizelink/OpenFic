import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const backend = process.env.OPENFIC_E2E_BACKEND ?? "http://127.0.0.1:8021";
const api = `${backend}/api/v1`;
const root = fileURLToPath(new URL("../../", import.meta.url));
test.use({ video: "off" });

async function bridge(
  page: Page,
  method: string,
  params: Record<string, unknown> = {},
  capabilities = ["ui", "editor.read", "editor.write"],
) {
  return page.evaluate(
    async (input) => {
      const path = "/src/features/plugins/frontend-host.ts";
      const host = (await import(path)) as {
        frontendCall(
          method: string,
          params: Record<string, unknown>,
          capabilities: string[],
          navigate: (path: string) => void,
        ): Promise<unknown>;
      };
      try {
        return {
          result: await host.frontendCall(input.method, input.params, input.capabilities, () => {}),
        };
      } catch (error) {
        return { error: String(error) };
      }
    },
    { method, params, capabilities },
  );
}

for (const mode of ["absent", "disabled", "enabled"] as const) {
  test(`original chapter/note editing, saves and capability boundaries with plugin ${mode}`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.request.delete(`${api}/plugins/regression-probe`);
    await page.request.delete(`${api}/plugins/regression-ui-only`);
    const projectResponse = await page.request.post(`${api}/projects`, {
      multipart: { title: `编辑器回归-${mode}` },
    });
    expect(projectResponse.ok()).toBeTruthy();
    const project = await projectResponse.json();
    try {
      if (mode !== "absent") {
        const zip = "/tmp/openfic-regression-probe.zip";
        execFileSync("python3", [
          `${root}examples/plugins/build_package.py`,
          `${root}frontend/e2e/fixtures/plugin-regression`,
          zip,
        ]);
        const response = await page.request.post(`${api}/plugins`, {
          multipart: {
            trusted: "true",
            file: { name: "probe.zip", mimeType: "application/zip", buffer: readFileSync(zip) },
          },
        });
        expect(response.ok(), await response.text()).toBeTruthy();
        if (mode === "enabled")
          expect(
            (
              await page.request.patch(`${api}/plugins/regression-probe/enabled`, {
                data: { enabled: true },
              })
            ).ok(),
          ).toBeTruthy();
        if (mode === "enabled") {
          const uiZip = "/tmp/openfic-regression-ui-only.zip";
          execFileSync("python3", [
            "-c",
            `import json,sys,zipfile
with zipfile.ZipFile(sys.argv[1]) as source, zipfile.ZipFile(sys.argv[2], 'w') as target:
 for entry in source.namelist():
  data=source.read(entry)
  if entry=='plugin.json':
   m=json.loads(data);m.update(id='regression-ui-only',backend=None,capabilities=['ui']);m['views'][0]['title']='UI only probe';data=json.dumps(m).encode()
  target.writestr(entry,data)
`,
            zip,
            uiZip,
          ]);
          expect(
            (
              await page.request.post(`${api}/plugins`, {
                multipart: {
                  trusted: "true",
                  file: {
                    name: "ui.zip",
                    mimeType: "application/zip",
                    buffer: readFileSync(uiZip),
                  },
                },
              })
            ).ok(),
          ).toBeTruthy();
          expect(
            (
              await page.request.patch(`${api}/plugins/regression-ui-only/enabled`, {
                data: { enabled: true },
              })
            ).ok(),
          ).toBeTruthy();
        }
      }
      const volume = (
        await (await page.request.get(`${api}/projects/${project.id}/volumes`)).json()
      )[0];
      const chapters: { id: string; title: string }[] = [];
      for (const title of ["回归甲", "回归乙"]) {
        const response = await page.request.post(`${api}/projects/${project.id}/chapters`, {
          data: { volume_id: volume.id, title, content: `${title}初始正文`, word_count: 7 },
        });
        expect(response.ok()).toBeTruthy();
        chapters.push(await response.json());
      }
      const noteResponse = await page.request.post(`${api}/projects/${project.id}/notes`, {
        data: { title: "回归笔记", content: "笔记初始正文" },
      });
      expect(noteResponse.ok()).toBeTruthy();
      const note = await noteResponse.json();
      await page.goto(`/projects/${project.id}`);
      await page.getByText("章节", { exact: true }).first().click();
      await page.getByText("回归甲", { exact: true }).first().click();
      const editor = page.locator('.chapter-editor-content .tiptap[contenteditable="true"]');
      await expect(editor).toContainText("回归甲初始正文");
      // Context is still available without granting editor contents.
      const hidden = await bridge(page, "ui.context", {}, ["ui"]);
      expect(hidden.result).toMatchObject({ editor: null, pathname: `/projects/${project.id}` });
      expect(
        (await bridge(page, "editor.setContent", { text: "forbidden" }, ["ui", "editor.read"]))
          .error,
      ).toContain("editor.write");
      if (mode === "enabled") {
        const uiButton = page
          .locator('[data-plugin-slot="editor.toolbar"]')
          .getByRole("button", { name: "UI only probe" });
        await uiButton.click();
        const uiFrame = page.frameLocator('iframe[title="UI only probe"]');
        await expect(uiFrame.getByRole("status")).toHaveText("Ready");
        const result = await uiFrame.locator("main").evaluate(async () => {
          const sdk = (
            window as unknown as {
              OpenFic: {
                ui: { context(): Promise<{ editor: unknown }> };
                editor: { read(): Promise<unknown> };
              };
            }
          ).OpenFic;
          const context = await sdk.ui.context();
          let error = "";
          try {
            await sdk.editor.read();
          } catch (fault) {
            error = String(fault);
          }
          return { context, error };
        });
        expect(result.context.editor).toBeNull();
        expect(result.error).toContain("editor.read");
        await uiButton.click();
        await page
          .locator('[data-plugin-slot="editor.toolbar"]')
          .getByRole("button", { name: "Regression probe" })
          .click();
        await expect(
          page.frameLocator('iframe[title="Regression probe"]').getByRole("status"),
        ).toHaveText("Ready");
      }
      await editor.fill("手动编辑正文，验证自动保存。");
      await expect
        .poll(
          async () =>
            (await (await page.request.get(`${api}/chapters/${chapters[0].id}`)).json()).content,
        )
        .toContain("手动编辑正文，验证自动保存。");
      await editor.press("End");
      await editor.pressSequentially("撤销重做验证", { delay: 20 });
      await page.getByRole("button", { name: "撤销", exact: true }).first().click();
      await expect(editor).not.toContainText("撤销重做验证");
      await page.getByRole("button", { name: "重做", exact: true }).first().click();
      await expect(editor).toContainText("撤销重做验证");
      await editor.press("Control+s");
      await expect
        .poll(
          async () =>
            (await (await page.request.get(`${api}/chapters/${chapters[0].id}`)).json()).content,
        )
        .toContain("撤销重做验证");
      await page.getByText("回归乙", { exact: true }).first().click();
      await expect(editor).toContainText("回归乙初始正文");
      await editor.fill("乙章节自己的修改");
      await editor.press("Control+s");
      await expect
        .poll(
          async () =>
            (await (await page.request.get(`${api}/chapters/${chapters[1].id}`)).json()).content,
        )
        .toContain("乙章节自己的修改");
      await page.getByText("回归甲", { exact: true }).first().click();
      await expect(editor).toContainText("撤销重做验证");
      await page.getByText("笔记", { exact: true }).first().click();
      await page.getByText("回归笔记", { exact: true }).first().click();
      const noteEditor = page.locator('.markdown-editor-content .tiptap[contenteditable="true"]');
      await expect(noteEditor).toContainText("笔记初始正文");
      await noteEditor.fill("笔记手动编辑并保存");
      await noteEditor.press("Control+s");
      await expect
        .poll(
          async () => (await (await page.request.get(`${api}/notes/${note.id}`)).json()).content,
        )
        .toContain("笔记手动编辑并保存");
      await expect
        .poll(async () => (await bridge(page, "editor.read")).result)
        .toMatchObject({
          kind: "note",
          id: note.id,
        });
      await page.reload();
      await expect(noteEditor).toContainText("笔记手动编辑并保存");
      await expect(page.locator(".ai-sidebar-input-area")).toBeVisible();
      expect(errors).toEqual([]);
    } finally {
      await page.request.delete(`${api}/plugins/regression-probe`);
      await page.request.delete(`${api}/plugins/regression-ui-only`);
      await page.request.delete(`${api}/projects/${project.id}`);
    }
  });
}
