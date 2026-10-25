import assert from "node:assert/strict";
import fs from "node:fs";
import { registerHooks, syncBuiltinESMExports } from "node:module";
import os from "node:os";
import path from "node:path";
import { finished } from "node:stream/promises";
import test from "node:test";

// Logging only needs app.getPath; the tests provide the active data directory.
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === "electron") {
      return { url: "data:text/javascript,export const app = { getPath() { throw new Error('Set logs directory'); } };", shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
});
const { appendLog, createLogStream, setLogsDir } = await import("../../dist/main/logging.js");
hook.deregister();

const BOM = Buffer.from([0xef, 0xbb, 0xbf]);

function dataDir(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "openfic-logging-"));
  fs.mkdirSync(path.join(dir, "logs"));
  setLogsDir(dir);
  t.after(() => {
    setLogsDir(null);
    fs.rmSync(dir, { recursive: true, force: true });
  });
  return path.join(dir, "logs", "backend.log");
}

function trackIO(t) {
  const reads = [];
  const originals = { readFileSync: fs.readFileSync, readSync: fs.readSync, appendFileSync: fs.appendFileSync };
  let wholeReads = 0;
  let appends = 0;
  fs.readFileSync = (...args) => { wholeReads += 1; return originals.readFileSync(...args); };
  fs.readSync = (...args) => { reads.push(args[3]); return originals.readSync(...args); };
  fs.appendFileSync = (...args) => { appends += 1; return originals.appendFileSync(...args); };
  syncBuiltinESMExports();
  t.after(() => {
    Object.assign(fs, originals);
    syncBuiltinESMExports();
  });
  return { reads, get wholeReads() { return wholeReads; }, get appends() { return appends; } };
}

test("1000 appends to a large log read only three-byte headers", (t) => {
  const file = dataDir(t);
  fs.writeFileSync(file, Buffer.concat([BOM, Buffer.alloc(5 * 1024 * 1024, 120)]));
  const io = trackIO(t);
  for (let i = 0; i < 1000; i += 1) appendLog("backend", `line ${i}`);
  assert.equal(io.wholeReads, 0);
  assert.equal(io.reads.length, 1000);
  assert.ok(io.reads.every((size) => size === 3));
  assert.equal(io.appends, 1000);
});

test("a traceback chunk is appended once and split lines survive stream finalization", async (t) => {
  const file = dataDir(t);
  const io = trackIO(t);
  const stream = createLogStream("backend");
  stream.write("first\n\nsecond\npar");
  stream.end("tial");
  await finished(stream);
  assert.equal(io.appends, 2);
  assert.equal(io.wholeReads, 0);
  const content = fs.readFileSync(file, "utf8");
  assert.ok(content.startsWith("\ufeff"));
  assert.match(content, /\] first\n/);
  assert.match(content, /\] second\n/);
  assert.match(content, /\] partial\n$/);
  assert.equal(content.split("\n").length, 4);
});

test("legacy BOM migration preserves content and happens only once", (t) => {
  const file = dataDir(t);
  fs.writeFileSync(file, "历史日志\n");
  const io = trackIO(t);
  appendLog("backend", "new line");
  appendLog("backend", "another line");
  assert.equal(io.wholeReads, 1);
  assert.match(fs.readFileSync(file, "utf8"), /^\ufeff历史日志\n/);
});

test("rotation preserves the archive and initializes the new BOM", (t) => {
  const file = dataDir(t);
  fs.writeFileSync(file, Buffer.concat([BOM, Buffer.alloc(10 * 1024 * 1024, 120)]));
  const io = trackIO(t);
  appendLog("backend", "after rotation");
  assert.equal(io.wholeReads, 0);
  const archives = fs.readdirSync(path.dirname(file)).filter((name) => name !== "backend.log");
  assert.equal(archives.length, 1);
  assert.match(fs.readFileSync(file, "utf8"), /^\ufeff\[.*\] after rotation\n$/);
  assert.equal(fs.statSync(path.join(path.dirname(file), archives[0])).size, 10 * 1024 * 1024 + 3);
});
