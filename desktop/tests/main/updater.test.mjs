import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import test from "node:test";

const state = globalThis.openficUpdateTest = {
  preference: "mirror", requests: [], downloads: [], events: [], failApi: null, failDownload: null, cancelDownload: false,
};
const metadata = { version: "0.12.2", files: [{ url: "OpenFic-0.12.2-win-x86_64-setup.exe", sha512: "same-checksum", size: 123 }] };
state.fetch = async (url) => {
  state.requests.push(String(url));
  if (state.failApi && String(url).includes(state.failApi)) return new Response("Unavailable", { status: 503 });
  return new Response(JSON.stringify(String(url).endsWith(".yml") ? metadata : { tag_name: "v0.12.2", body: "Notes" }));
};

const mockUpdater = `
import { EventEmitter } from 'node:events';
const state = globalThis.openficUpdateTest;
export class CancellationToken { cancelled = false; cancel() { this.cancelled = true; } }
export class NsisUpdater extends EventEmitter {
  netSession = { fetch: (...args) => state.fetch(...args), setProxy: async () => {} };
  setFeedURL(options) { this.options = options; }
  async checkForUpdates() {
    this.provider = new this.options.updateProvider(this.options, this, { executor: {}, platform: 'win32' });
    this.info = await this.provider.getLatestVersion();
    return { isUpdateAvailable: true, updateInfo: this.info };
  }
  async downloadUpdate(token) {
    const url = this.provider.resolveFiles(this.info)[0].url.href;
    state.downloads.push(url);
    if (state.cancelDownload) { token.cancel(); throw new Error('cancelled'); }
    if (state.failDownload && url.includes(state.failDownload)) {
      this.emit('error', new Error('source download failed'));
      throw new Error('source download failed');
    }
    this.emit('update-downloaded', this.info);
    return ['installer.exe'];
  }
}
export const autoUpdater = new NsisUpdater();
export default { autoUpdater };
`;
const asModule = (code) => ({ url: `data:text/javascript,${encodeURIComponent(code)}`, shortCircuit: true });
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === "electron-updater") return asModule(mockUpdater);
    if (specifier === "electron") return asModule(`
      export const app = { isPackaged: true, getPath: () => 'C:/openfic-test/OpenFic.exe' };
      export const shell = { openExternal: async () => {} };
      export const net = { fetch: (...args) => globalThis.openficUpdateTest.fetch(...args) };
    `);
    if (specifier === "./config.js" && context.parentURL.endsWith("download-sources.js")) {
      return asModule(`export const readDesktopConfig = async () => ({ downloadSource: globalThis.openficUpdateTest.preference });`);
    }
    if (specifier === "./proxy.js") return asModule(`export const configureSystemProxy = async () => {}; export const configureDefaultSystemProxy = async () => {};`);
    if (specifier === "./logging.js") return asModule(`export const appendLog = () => {};`);
    return nextResolve(specifier, context);
  },
});
const updater = await import("../../dist/main/updater.js");
hook.deregister();
await updater.initializeUpdater({ webContents: { send: (_channel, data) => state.events.push(data) } });

function reset(preference = "mirror") {
  Object.assign(state, { preference, failApi: null, failDownload: null, cancelDownload: false, requests: [], downloads: [], events: [] });
}

test("mirror preference gets AtomGit version, metadata and notes without requesting GitHub", async () => {
  reset();
  await updater.checkForUpdates();
  assert.equal(updater.getUpdateState().status, "available");
  assert.equal(updater.getUpdateState().releaseNotes, "Notes");
  assert.ok(state.requests.every((url) => url.includes("atomgit.com")));
});

test("unavailable preferred API falls back to the other release source", async () => {
  reset();
  state.failApi = "api.atomgit.com";
  await updater.checkForUpdates();
  assert.equal(updater.getUpdateState().status, "available");
  assert.ok(state.requests[0].includes("api.atomgit.com"));
  assert.ok(state.requests.some((url) => url.includes("api.github.com")));
});

test("cancelling download restores the available state and never tries fallback", async () => {
  reset();
  await updater.checkForUpdates();
  state.cancelDownload = true;
  await updater.downloadUpdate();
  assert.equal(updater.getUpdateState().status, "available");
  assert.equal(state.downloads.length, 1);
});

test("download failure retries the same version on the alternate source without publishing an error", async () => {
  reset("default");
  await updater.checkForUpdates();
  // A preference change after checking must apply to the actual download too.
  state.preference = "mirror";
  state.failDownload = "atomgit.com";
  await updater.downloadUpdate();
  assert.equal(updater.getUpdateState().status, "downloaded");
  assert.equal(state.downloads.length, 2);
  assert.ok(state.downloads[0].includes("atomgit.com"));
  assert.ok(state.downloads[1].includes("github.com"));
  assert.ok(state.downloads.every((url) => url.includes("v0.12.2/OpenFic-0.12.2-win-x86_64-setup.exe")));
  assert.ok(!state.events.some(({ status }) => status === "error"));
});
