import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

const backend = process.env.OPENFIC_E2E_BACKEND ?? "http://127.0.0.1:8042";
const api = backend + "/api/v1";
test.use({ video: "off" });

function build(mode: "legacy" | "unified") {
  const filename = `/tmp/openfic-layout-${mode}.zip`;
  execFileSync("python3", [
    "-c",
    `import base64,json,sys,zipfile
mode,path=sys.argv[1:]
legacy=mode=='legacy'
entry='backend/main.py' if legacy else 'main.py'
view='frontend/index.html' if legacy else 'panels/custom view/index.html'
asset='frontend/assets/pixel.gif' if legacy else 'assets/pixel.gif'
manifest={'id':'layout-migration','name':'Layout migration','version':'1.0.0' if legacy else '1.1.0','api_version':1,'capabilities':['ui','storage'],'views':[{'id':'panel','title':'Layout migration','entry':view,'slot':'sidebar.extensions'}]}
manifest['backend' if legacy else 'entry']=entry
if not legacy:manifest['resources']=['panels','assets']
html='<!doctype html><html><head><meta charset="utf-8">'+('<script src="../../sdk.js" defer></script>' if legacy else '')+'</head><body><h1>'+('Legacy view' if legacy else 'Unified view')+'</h1><output>Loading</output><button id="increment">Increment</button><img alt="Package image"><script src="./app.js" defer crossorigin="anonymous"></script></body></html>'
js='''void OpenFic.ready.then(async () => {
 let count = Number(await OpenFic.storage.get('count', 0));
 const output = document.querySelector('output'); output.textContent = String(count);
 document.querySelector('#increment').onclick = async () => { await OpenFic.storage.set('count', ++count); output.textContent = String(count); };
 const asset = await OpenFic.assets.read('assets/pixel.gif');
 document.querySelector('img').src = 'data:' + asset.mime + ';base64,' + asset.base64;
});'''
with zipfile.ZipFile(path,'w') as z:
 z.writestr('plugin.json',json.dumps(manifest));z.writestr(entry,'def register(host): pass\\n');z.writestr(view,html);z.writestr(view.rsplit('/',1)[0]+'/app.js',js);z.writestr(asset,base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'));z.writestr('private.json','{"private":true}')
`,
    mode,
    filename,
  ]);
  return readFileSync(filename);
}

async function install(page: Page, mode: "legacy" | "unified") {
  const response = await page.request[mode === "legacy" ? "post" : "put"](
    mode === "legacy" ? `${api}/plugins` : `${api}/plugins/layout-migration/package`,
    {
      multipart: {
        trusted: "true",
        file: { name: `${mode}.zip`, mimeType: "application/zip", buffer: build(mode) },
      },
    },
  );
  expect(response.ok(), await response.text()).toBeTruthy();
}

test("legacy iframe SDK and asset paths survive an upgrade to a unified nested package", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.request.delete(`${api}/plugins/layout-migration`);
  try {
    await install(page, "legacy");
    expect(
      (
        await page.request.patch(`${api}/plugins/layout-migration/enabled`, {
          data: { enabled: true },
        })
      ).ok(),
    ).toBeTruthy();
    await page.goto("/extensions/layout-migration/panel");
    const frame = page.frameLocator('iframe[title="Layout migration"]');
    await expect(frame.getByRole("heading", { name: "Legacy view" })).toBeVisible();
    await expect(frame.locator("output")).toHaveText("0");
    await expect(frame.getByAltText("Package image")).toHaveJSProperty("naturalWidth", 1);
    await frame.getByRole("button", { name: "Increment" }).click();
    await expect(frame.locator("output")).toHaveText("1");
    await install(page, "unified");
    await page.reload();
    await expect(frame.getByRole("heading", { name: "Unified view" })).toBeVisible();
    await expect(frame.locator("output")).toHaveText("1");
    await expect(frame.getByAltText("Package image")).toHaveJSProperty("naturalWidth", 1);
    await frame.getByRole("button", { name: "Increment" }).click();
    await expect(frame.locator("output")).toHaveText("2");
    for (const path of ["main.py", "plugin.json", "private.json"])
      expect(
        (await page.request.get(`${api}/plugins/layout-migration/assets/${path}`)).status(),
      ).toBe(404);
    const opened = await page.request.post(`${api}/plugins/layout-migration/views/panel`);
    const url = (await opened.json()).url as string;
    expect(url).toContain("panels/custom%20view/index.html");
    const html = await page.request.get(backend + url);
    expect((await html.text()).match(/\/sdk\.js/g)).toHaveLength(1);
    expect(errors).toEqual([]);
  } finally {
    await page.request.delete(`${api}/plugins/layout-migration`);
  }
});
