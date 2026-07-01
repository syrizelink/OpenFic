import { spawn } from "node:child_process";
import { access, mkdir } from "node:fs/promises";
import path from "node:path";
import { findFreePort } from "../ports.js";
import { startBackendProcess, type BackendProcessHandle } from "../process.js";
import { waitForBackend } from "../health.js";
import type { PortablePython } from "./python.js";
import { createOpenFicInstallCommand, createOpenFicProbeCommand, createOpenFicServeCommand } from "./openfic-commands.js";

export type OpenFicRuntimeStep = "create-venv" | "install-uv" | "install-openfic";

function getVenvDir(runtimeDir: string): string {
  return path.join(runtimeDir, "venv");
}

function getVenvPythonPath(runtimeDir: string): string {
  if (process.platform === "win32") return path.join(getVenvDir(runtimeDir), "Scripts", "python.exe");
  return path.join(getVenvDir(runtimeDir), "bin", "python");
}

function getUvPath(runtimeDir: string): string {
  if (process.platform === "win32") return path.join(getVenvDir(runtimeDir), "Scripts", "uv.exe");
  return path.join(getVenvDir(runtimeDir), "bin", "uv");
}

export function resolveUvPath(runtimeDir: string): string {
  return getUvPath(runtimeDir);
}

export function resolveVenvPythonPath(runtimeDir: string): string {
  return getVenvPythonPath(runtimeDir);
}

async function pathExists(filePath: string): Promise<boolean> {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

function forwardLines(
  stream: NodeJS.ReadableStream | null,
  writer: NodeJS.WriteStream,
  onLine?: (line: string) => void,
): void {
  if (!stream) return;

  let buffer = "";
  stream.on("data", (chunk: Buffer | string) => {
    const text = typeof chunk === "string" ? chunk : chunk.toString("utf8");
    writer.write(text);
    buffer += text.replace(/\r/g, "\n");

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) onLine?.(trimmed);
    }
  });

  stream.on("end", () => {
    const trimmed = buffer.trim();
    if (trimmed) onLine?.(trimmed);
  });
}

function stripAnsi(value: string): string {
  return value.replace(/\u001b\[[0-9;]*[A-Za-z]/g, "");
}

function run(command: string, args: string[], cwd: string, onStdoutLine?: (line: string) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    forwardLines(child.stdout, process.stdout, (line) => {
      const text = stripAnsi(line).trim();
      if (text) onStdoutLine?.(text);
    });
    forwardLines(child.stderr, process.stderr);
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
  runtimeDir: string,
  onProgress: (step: OpenFicRuntimeStep, message: string) => void,
): Promise<{ uvPath: string; venvPythonPath: string }> {
  const venvDir = getVenvDir(runtimeDir);
  const venvPythonPath = getVenvPythonPath(runtimeDir);
  const uvPath = getUvPath(runtimeDir);

  await mkdir(runtimeDir, { recursive: true });

  if (!(await pathExists(venvPythonPath))) {
    onProgress("create-venv", "创建 OpenFic 运行环境");
    await run(python.pythonPath, ["-m", "venv", venvDir], runtimeDir);
  }

  if (!(await pathExists(uvPath))) {
    onProgress("install-uv", "安装 uv");
    await run(venvPythonPath, ["-m", "pip", "install", "uv"], runtimeDir, (message) => onProgress("install-uv", message));
  }

  const probeCommand = createOpenFicProbeCommand(venvPythonPath);
  if (!(await succeeds(probeCommand.command, probeCommand.args, runtimeDir))) {
    onProgress("install-openfic", "安装 OpenFic 后端");
    const installCommand = createOpenFicInstallCommand(venvPythonPath);
    await run(uvPath, installCommand.args, runtimeDir, (message) => onProgress("install-openfic", message));
  }

  return { uvPath, venvPythonPath };
}

export async function startLocalOpenFicBackend(venvPythonPath: string): Promise<BackendProcessHandle> {
  const port = await findFreePort();
  const command = createOpenFicServeCommand(venvPythonPath, port);
  const handle = startBackendProcess({
    command: command.command,
    args: command.args,
    port,
  });
  await waitForBackend(handle.baseUrl, { process: handle.process });
  return handle;
}
