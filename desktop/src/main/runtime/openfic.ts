import { spawn } from "node:child_process";
import { access, mkdir } from "node:fs/promises";
import path from "node:path";
import { findFreePort } from "../ports.js";
import { startBackendProcess, type BackendProcessHandle } from "../process.js";
import { waitForBackend } from "../health.js";
import type { PortablePython } from "./python.js";

const electron = require("electron") as typeof import("electron");

const { app } = electron;

export type OpenFicRuntimeStep = "create-venv" | "install-uv" | "install-openfic";

function getVenvDir(): string {
  return path.join(app.getPath("userData"), "runtime", "venv");
}

function getVenvPythonPath(): string {
  if (process.platform === "win32") return path.join(getVenvDir(), "Scripts", "python.exe");
  return path.join(getVenvDir(), "bin", "python");
}

function getUvPath(): string {
  if (process.platform === "win32") return path.join(getVenvDir(), "Scripts", "uv.exe");
  return path.join(getVenvDir(), "bin", "uv");
}

async function pathExists(filePath: string): Promise<boolean> {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

function run(command: string, args: string[], cwd: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      windowsHide: true,
      stdio: "inherit",
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} ${args.join(" ")} exited with code ${code}`));
    });
  });
}

function succeeds(command: string, args: string[], cwd: string): Promise<boolean> {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd,
      windowsHide: true,
      stdio: "ignore",
    });
    child.on("error", () => resolve(false));
    child.on("exit", (code) => resolve(code === 0));
  });
}

export async function ensureOpenFicRuntime(
  python: PortablePython,
  onProgress: (step: OpenFicRuntimeStep, message: string) => void,
): Promise<{ uvPath: string }> {
  const runtimeDir = path.join(app.getPath("userData"), "runtime");
  const venvDir = getVenvDir();
  const venvPythonPath = getVenvPythonPath();
  const uvPath = getUvPath();

  await mkdir(runtimeDir, { recursive: true });

  if (!(await pathExists(venvPythonPath))) {
    onProgress("create-venv", "创建 OpenFic 运行环境");
    await run(python.pythonPath, ["-m", "venv", venvDir], runtimeDir);
  }

  if (!(await pathExists(uvPath))) {
    onProgress("install-uv", "安装 uv");
    await run(venvPythonPath, ["-m", "pip", "install", "uv"], runtimeDir);
  }

  if (!(await succeeds(uvPath, ["pip", "show", "openfic"], runtimeDir))) {
    onProgress("install-openfic", "安装 OpenFic 后端");
    await run(uvPath, ["pip", "install", "openfic"], runtimeDir);
  }

  return { uvPath };
}

export async function startLocalOpenFicBackend(uvPath: string): Promise<BackendProcessHandle> {
  const port = await findFreePort();
  const handle = startBackendProcess({
    command: uvPath,
    args: ["run", "openfic", "serve", "--host", "127.0.0.1", "--port", String(port)],
    port,
  });
  await waitForBackend(handle.baseUrl);
  return handle;
}
