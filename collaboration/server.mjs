import { Server } from "@hocuspocus/server";
import * as Y from "yjs";
import { createInterface } from "node:readline";
import { seed, textOf, validate, replaceExact, replaceRange } from "./document.mjs";

// Stdout is exclusively the parent/worker RPC transport.
console.log = (...args) => console.error(...args);
const send = (value) => process.stdout.write(JSON.stringify(value) + "\n");
const pending = new Map();
let requestId = 0;
function call(method, data) {
  const id = ++requestId;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error("Persistence timed out"));
    }, 30000);
    pending.set(id, { resolve, reject, timer });
    send({ requestId: id, method, ...data });
  });
}
const versions = new WeakMap();
const directConnections = new Map();
const seeds = new Map();
const releaseTimers = new Map();
const retired = new WeakSet();
let paused = false;
function snapshot(document) {
  return {
    room: document.name,
    state: Buffer.from(Y.encodeStateAsUpdate(document)).toString("base64"),
    content: textOf(document),
    version: versions.get(document) ?? 0,
  };
}
async function store(document) {
  if (retired.has(document)) return;
  try {
    validate(document);
    const saved = snapshot(document);
    await call("store", saved);
    document.broadcastStateless(
      JSON.stringify({
        type: "saved",
        version: saved.version,
        content: saved.content,
        vector: [...Y.encodeStateVectorFromUpdate(Buffer.from(saved.state, "base64"))],
      }),
    );
  } catch (error) {
    if (error.message.includes("协同文档") || error.message.includes("章节不存在")) {
      retired.add(document);
      server.hocuspocus.closeConnections(document.name);
      return;
    }
    document.broadcastStateless(JSON.stringify({ type: "error", message: error.message }));
    console.error(error);
    setTimeout(() => {
      if (!document.isDestroyed && !paused) void store(document);
    }, 2000).unref();
  }
}
const server = new Server({
  address: "127.0.0.1",
  port: 0,
  quiet: true,
  debounce: 200,
  maxDebounce: 1000,
  async onConnect({ requestParameters }) {
    if (paused || requestParameters.get("secret") !== process.env.OPENFIC_COLLABORATION_SECRET)
      throw new Error("Unauthorized");
  },
  async onAuthenticate({ documentName, requestParameters }) {
    if (documentName !== requestParameters.get("room")) throw new Error("Invalid chapter room");
  },
  async onLoadDocument({ document, documentName }) {
    const saved = seeds.get(documentName) ?? (await call("load", { room: documentName }));
    seeds.delete(documentName);
    versions.set(document, saved.version);
    if (saved.state) Y.applyUpdate(document, Buffer.from(saved.state, "base64"));
    else seed(document, saved.content);
    return document;
  },
  beforeHandleMessage({ document }) {
    if (paused) throw new Error("Collaboration is disabled");
    // Client content is validated again before persistence.
    if (textOf(document).length > 200000) throw new Error("Document too large");
  },
  onChange({ document }) {
    versions.set(document, (versions.get(document) ?? 0) + 1);
  },
  async onStateless({ document, payload }) {
    if (payload === JSON.stringify({ type: "flush" })) await store(document);
  },
  async onStoreDocument({ document }) {
    await store(document);
  },
});
async function command(message) {
  if (message.method === "pause") {
    paused = true;
    const snapshots = [...server.hocuspocus.documents.values()].map(snapshot);
    server.hocuspocus.closeConnections();
    return snapshots;
  }
  if (message.method === "resume") {
    paused = false;
    return true;
  }
  if (message.method === "health") return true;
  if (message.method === "evict") {
    server.hocuspocus.closeConnections(message.room);
    const document = server.hocuspocus.documents.get(message.room);
    if (document) {
      retired.add(document);
      const connection = directConnections.get(message.room);
      directConnections.delete(message.room);
      if (connection) await connection.disconnect();
      await server.hocuspocus.unloadDocument(document);
    }
    return true;
  }
  const existing = server.hocuspocus.documents.get(message.room);
  if (message.method === "snapshot" && existing) return snapshot(existing);
  if (message.seed) seeds.set(message.room, message.seed);
  let connection = directConnections.get(message.room);
  if (!connection) {
    connection = await server.hocuspocus.openDirectConnection(message.room, { rpc: true });
    directConnections.set(message.room, connection);
  }
  seeds.delete(message.room);
  clearTimeout(releaseTimers.get(message.room));
  releaseTimers.set(
    message.room,
    setTimeout(() => {
      const active = directConnections.get(message.room);
      directConnections.delete(message.room);
      releaseTimers.delete(message.room);
      if (active) void active.disconnect().catch(console.error);
    }, 30000).unref(),
  );
  const live = connection.document;
  if (message.method === "snapshot") return snapshot(live);
  if (message.method === "apply") {
    Y.applyUpdate(live, Buffer.from(message.state, "base64"), "agent");
    return snapshot(live);
  }
  // Prepare against the latest live state, but publish only after the SQL
  // transaction (snapshot + binary state + Agent revision) has committed.
  const candidate = new Y.Doc();
  Y.applyUpdate(candidate, Y.encodeStateAsUpdate(live));
  try {
    let result;
    if (message.method === "edit")
      result = replaceExact(
        candidate,
        message.old_content,
        message.new_content,
        message.replace_all,
      );
    else if (message.method === "restore") {
      const before = textOf(candidate);
      for (const edit of message.edits) {
        const current = textOf(candidate);
        let needle = edit.left + edit.old + edit.right;
        let at = needle ? current.indexOf(needle) : -1;
        let from = at + edit.left.length;
        if (at < 0 || current.indexOf(needle, at + 1) >= 0) {
          needle = edit.old;
          at = edit.unique && needle ? current.indexOf(needle) : -1;
          from = at;
        }
        if (at < 0 || current.indexOf(needle, at + 1) >= 0)
          throw new Error(
            "Rollback conflicts with current edits; resolve the chapter changes first",
          );
        candidate.transact(
          () => replaceRange(candidate, from, from + edit.old.length, edit.text),
          "agent",
        );
      }
      result = { before, content: textOf(candidate) };
    } else throw new Error("Unknown worker method");
    validate(candidate);
    const version = (versions.get(live) ?? 0) + 1;
    versions.set(live, version);
    return { ...result, ...snapshot(candidate), room: message.room, version };
  } finally {
    candidate.destroy();
  }
}
createInterface({ input: process.stdin }).on("line", async (line) => {
  try {
    const message = JSON.parse(line);
    if (message.requestId) {
      const item = pending.get(message.requestId);
      if (!item) return;
      pending.delete(message.requestId);
      clearTimeout(item.timer);
      if (message.error) item.reject(new Error(message.error));
      else item.resolve(message.result);
      return;
    }
    try {
      send({ id: message.id, result: await command(message) });
    } catch (error) {
      send({ id: message.id, error: String(error.message ?? error) });
    }
  } catch (error) {
    console.error(error);
  }
});
process.stdin.on("end", () => process.exit(0));
server
  .listen()
  .then(() => send({ ready: true, port: server.address.port }))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
