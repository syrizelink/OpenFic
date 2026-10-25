import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { registerHooks } from "node:module";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const state = globalThis.openficRuntimeSourceTest = { preference: "mirror", installs: [], probes: [] };
const mockProcess = `
import { EventEmitter } from 'node:events';
import { PassThrough } from 'node:stream';
export function spawn(command, args, options) {
  const child = new EventEmitter();
  child.stdout = new PassThrough(); child.stderr = new PassThrough();
  queueMicrotask(() => {
    const state = globalThis.openficRuntimeSourceTest;
    if (args.includes('install')) {
      state.installs.push({ command, args, env: options.env });
      const fail = options.env.PIP_INDEX_URL.includes('mirrors.cernet.edu.cn');
      child.stdout.end(); child.stderr.end(fail ? 'mirror unavailable' : '');
      child.emit('exit', fail ? 1 : 0);
    } else {
      child.stdout.end(args.includes('-c') ? '0.12.0' : 'Python 3.13.14');
      child.stderr.end(); child.emit('exit', 0);
    }
  });
  return child;
}
`;
const moduleCode = (code) => ({ url: `data:text/javascript,${encodeURIComponent(code)}`, shortCircuit: true });
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === "node:child_process") return moduleCode(mockProcess);
    if (specifier === "electron") return moduleCode(`
      export const app = { getPath: () => '' };
      export const net = { fetch: async (url) => {
        globalThis.openficRuntimeSourceTest.probes.push(url);
        return new Response('openfic-0.12.1');
      }};
    `);
    if (specifier === "./config.js" && context.parentURL.endsWith("download-sources.js")) {
      return moduleCode(`export const readDesktopConfig = async () => ({downloadSource:globalThis.openficRuntimeSourceTest.preference});`);
    }
    if (specifier.endsWith("/proxy.js")) return moduleCode(`
      export const configureDefaultSystemProxy = async () => {};
      export const getSystemProxyEnvironment = async () => ({});
    `);
    if (specifier.endsWith("/logging.js")) return moduleCode(`
      import { Writable } from 'node:stream';
      export const appendLog = () => {};
      export const getLogPath = () => '';
      export const createLogStream = () => new Writable({write(_chunk,_encoding,done){done();}});
    `);
    return nextResolve(specifier, context);
  },
});
const { ensureOpenFicRuntime } = await import("../../dist/main/runtime/openfic.js");
hook.deregister();

test("uv and the pinned backend use the preferred PyPI index, then retry on the other index", async () => {
  const tempRoot = path.resolve(os.tmpdir());
  const directory = await mkdtemp(path.join(tempRoot, "openfic-source-test-"));
  try {
    const scripts = path.join(directory, "venv", process.platform === "win32" ? "Scripts" : "bin");
    await mkdir(scripts, { recursive: true });
    await writeFile(path.join(scripts, process.platform === "win32" ? "python.exe" : "python"), "");
    await writeFile(path.join(scripts, process.platform === "win32" ? "openfic.exe" : "openfic"), "");
    await ensureOpenFicRuntime({ pythonPath: "portable-python", wasReplaced: false }, directory, "0.12.1", () => {});
    assert.equal(state.installs.length, 4);
    const [uvMirror, uvDefault, backendMirror, backendDefault] = state.installs;
    for (const command of [uvMirror, backendMirror]) assert.equal(command.env.PIP_INDEX_URL, "https://mirrors.cernet.edu.cn/pypi/web/simple/");
    for (const command of [uvDefault, backendDefault]) assert.equal(command.env.UV_INDEX_URL, "https://pypi.org/simple/");
    assert.ok(uvMirror.args.includes("uv"));
    assert.ok(backendMirror.args.includes("openfic==0.12.1"));
    assert.equal(state.probes.length, 0, "Explicit preference must not be overridden by a speed probe");
  } finally {
    assert.ok(path.relative(tempRoot, path.resolve(directory)).startsWith("openfic-source-test-"));
    await rm(directory, { recursive: true, force: true });
  }
});
