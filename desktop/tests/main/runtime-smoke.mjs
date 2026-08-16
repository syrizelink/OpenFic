import { spawn } from "node:child_process";
import { access, mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { app } from "electron";
import { stopBackendProcess } from "../../dist/main/process.js";
import { startLocalOpenFicBackend } from "../../dist/main/runtime/openfic.js";
import { ensurePortablePython } from "../../dist/main/runtime/python.js";

const BACKEND_STOP_TIMEOUT_MS = 15_000;
const TEMP_DIRECTORY_REMOVE_RETRIES = 5;
const TEMP_DIRECTORY_REMOVE_RETRY_DELAY_MS = 200;

function run(command, args, cwd) {
  return new Promise((resolve, reject) => {
    const process = spawn(command, args, { cwd, stdio: "inherit" });
    process.on("error", reject);
    process.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`${command} ${args.join(" ")} exited with code ${code}`));
    });
  });
}

async function getWheelPath() {
  const wheelPath = process.argv[2];
  if (!wheelPath?.endsWith(".whl")) throw new Error("OpenFic wheel path is required");
  await access(wheelPath);
  return path.resolve(wheelPath);
}

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

async function readDesktopVersion() {
  const packageJson = JSON.parse(await readFile(new URL("../../package.json", import.meta.url), "utf8"));
  if (typeof packageJson.version !== "string") throw new Error("desktop package version is missing");
  return packageJson.version;
}

async function smokeTestRuntime() {
  const userDataDir = await mkdtemp(path.join(os.tmpdir(), "openfic-runtime-smoke-"));
  const runtimeDir = path.join(userDataDir, "runtime");
  const venvDir = path.join(runtimeDir, "venv");
  const venvPythonPath = path.join(venvDir, "bin", "python");
  const uvPath = path.join(venvDir, "bin", "uv");
  let backend = null;

  app.setPath("userData", userDataDir);

  try {
    await app.whenReady();
    const python = await ensurePortablePython(runtimeDir, (phase, message) => console.log(`${phase}: ${message}`), () => {});
    const expectedVersion = await readDesktopVersion();
    const wheelPath = await getWheelPath();
    console.log(`Installing OpenFic runtime ${expectedVersion} from ${wheelPath}`);
    await run(python.pythonPath, ["-m", "venv", venvDir], runtimeDir);
    await run(venvPythonPath, ["-m", "pip", "install", "uv"], runtimeDir);
    await run(uvPath, ["pip", "install", "--python", venvPythonPath, wheelPath], runtimeDir);

    const { handle } = await startLocalOpenFicBackend(venvPythonPath, expectedVersion);
    backend = handle;
    console.log(`OpenFic runtime smoke test passed: ${backend.baseUrl}`);
  } catch (error) {
    const backendLogPath = path.join(userDataDir, "logs", "backend.log");
    try {
      console.error(`Backend log:\n${await readFile(backendLogPath, "utf8")}`);
    } catch {
      // The backend may fail before its logger has written a file.
    }
    throw error;
  } finally {
    if (backend) {
      await stopBackend(backend);
    }
    await rm(userDataDir, {
      recursive: true,
      force: true,
      maxRetries: TEMP_DIRECTORY_REMOVE_RETRIES,
      retryDelay: TEMP_DIRECTORY_REMOVE_RETRY_DELAY_MS,
    });
  }
}

void smokeTestRuntime().then(
  () => app.quit(),
  (error) => {
    console.error(error);
    app.exit(1);
  },
);
