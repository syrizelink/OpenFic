import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { app } from "electron";
import { stopBackendProcess } from "../../dist/main/process.js";
import { ensureOpenFicRuntime, startLocalOpenFicBackend } from "../../dist/main/runtime/openfic.js";
import { ensurePortablePython } from "../../dist/main/runtime/python.js";

const BACKEND_STOP_TIMEOUT_MS = 15_000;

async function waitForBackendProcessToStop(backend, timeoutMs) {
  if (backend.process.exitCode !== null || backend.process.signalCode !== null) return;

  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error("backend process did not stop within timeout")), timeoutMs);
    backend.process.once("close", () => {
      clearTimeout(timeout);
      resolve();
    });
    if (backend.process.exitCode !== null || backend.process.signalCode !== null) {
      clearTimeout(timeout);
      resolve();
    }
  });
}

async function stopBackend(backend) {
  stopBackendProcess(backend);
  try {
    await waitForBackendProcessToStop(backend, BACKEND_STOP_TIMEOUT_MS);
  } catch {
    backend.process.kill("SIGKILL");
    await waitForBackendProcessToStop(backend, BACKEND_STOP_TIMEOUT_MS);
  }
}

async function smokeTestRuntime() {
  const userDataDir = await mkdtemp(path.join(os.tmpdir(), "openfic-runtime-smoke-"));
  const runtimeDir = path.join(userDataDir, "runtime");
  let backend = null;

  app.setPath("userData", userDataDir);

  try {
    await app.whenReady();
    const python = await ensurePortablePython(runtimeDir, (phase, message) => console.log(`${phase}: ${message}`), () => {});
    const expectedVersion = app.getVersion();
    console.log(`Installing OpenFic runtime ${expectedVersion}`);
    const { venvPythonPath } = await ensureOpenFicRuntime(python, runtimeDir, expectedVersion, (step, message) => {
      console.log(`${step}: ${message}`);
    });

    backend = await startLocalOpenFicBackend(venvPythonPath, expectedVersion);
    console.log(`OpenFic runtime smoke test passed: ${backend.baseUrl}`);
  } finally {
    if (backend) {
      await stopBackend(backend);
    }
    await rm(userDataDir, { recursive: true, force: true });
  }
}

void smokeTestRuntime().then(
  () => app.quit(),
  (error) => {
    console.error(error);
    app.exit(1);
  },
);
