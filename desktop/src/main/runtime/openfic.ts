import { spawn } from "node:child_process";
import { access, mkdir, rm } from "node:fs/promises";
import path from "node:path";
import { findFreePort } from "../ports.js";
import { startBackendProcess, stopBackendProcess, type BackendProcessHandle } from "../process.js";
import { getSystemProxyEnvironment } from "../proxy.js";
import { waitForBackend } from "../health.js";
import type { PortablePython, RuntimeIntegrityCheck } from "./python.js";
import {
  createOpenFicInstallCommand,
  createOpenFicServeCommand,
  createOpenFicVersionCommand,
  resolveOpenFicCliPath,
} from "./openfic-commands.js";
import type { StartupProgressTracker } from "../startup-progress.js";

export type OpenFicRuntimeStep = "create-venv" | "install-uv" | "install-openfic";

const ANSI_ESCAPE_SEQUENCE = new RegExp(`${String.fromCharCode(0x1b)}\\[[0-9;]*[A-Za-z]`, "g");

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
  return value.replace(ANSI_ESCAPE_SEQUENCE, "");
}

function run(
  command: string,
  args: string[],
  cwd: string,
  onStdoutLine?: (line: string) => void,
  environment?: NodeJS.ProcessEnv,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      env: { ...process.env, ...environment },
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

function readOutput(command: string, args: string[], cwd: string): Promise<string | null> {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd,
      windowsHide: true,
      stdio: ["ignore", "pipe", "ignore"],
    });
    let output = "";
    child.stdout.on("data", (chunk: Buffer | string) => {
      output += typeof chunk === "string" ? chunk : chunk.toString("utf8");
    });
    child.on("error", () => resolve(null));
    child.on("exit", (code) => resolve(code === 0 ? output.trim() || null : null));
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

export async function inspectOpenFicRuntime(
  runtimeDir: string,
  expectedVersion: string,
): Promise<RuntimeIntegrityCheck> {
  const venvPythonPath = getVenvPythonPath(runtimeDir);
  if (!(await pathExists(venvPythonPath))) {
    return { complete: false, message: "未找到 Python 虚拟环境" };
  }
  if (!(await readOutput(venvPythonPath, ["--version"], runtimeDir))) {
    return { complete: false, message: "Python 虚拟环境不可用" };
  }

  const uvPath = getUvPath(runtimeDir);
  if (!(await pathExists(uvPath)) || !(await readOutput(uvPath, ["--version"], runtimeDir))) {
    return { complete: false, message: "uv 不存在或不可用" };
  }

  const versionCommand = createOpenFicVersionCommand(venvPythonPath);
  const installedVersion = await readOutput(versionCommand.command, versionCommand.args, runtimeDir);
  if (installedVersion !== expectedVersion) {
    return {
      complete: false,
      message: installedVersion ? "OpenFic 后端版本不匹配" : "未找到 OpenFic 后端",
    };
  }
  const openFicCliPath = resolveOpenFicCliPath(venvPythonPath);
  if (!(await pathExists(openFicCliPath)) || !(await succeeds(openFicCliPath, ["--help"], runtimeDir))) {
    return { complete: false, message: "OpenFic 命令行程序缺失或不可用" };
  }

  return { complete: true, message: "OpenFic 运行环境已完整安装" };
}

export async function ensureOpenFicRuntime(
  python: PortablePython,
  runtimeDir: string,
  expectedVersion: string,
  onProgress: (step: OpenFicRuntimeStep, message: string) => void,
): Promise<{ uvPath: string; venvPythonPath: string }> {
  const venvDir = getVenvDir(runtimeDir);
  const venvPythonPath = getVenvPythonPath(runtimeDir);
  const uvPath = getUvPath(runtimeDir);

  await mkdir(runtimeDir, { recursive: true });

  if (python.wasReplaced) await rm(venvDir, { recursive: true, force: true });

  const venvIsUsable =
    (await pathExists(venvPythonPath)) && Boolean(await readOutput(venvPythonPath, ["--version"], runtimeDir));
  if (!venvIsUsable) {
    await rm(venvDir, { recursive: true, force: true });
    onProgress("create-venv", "创建 OpenFic 运行环境");
    await run(python.pythonPath, ["-m", "venv", venvDir], runtimeDir);
  }

  const uvIsUsable = (await pathExists(uvPath)) && Boolean(await readOutput(uvPath, ["--version"], runtimeDir));
  if (!uvIsUsable) {
    onProgress("install-uv", "安装 uv");
    const proxyEnvironment = await getSystemProxyEnvironment("https://pypi.org/");
    await run(
      venvPythonPath,
      ["-m", "pip", "install", "--force-reinstall", "uv"],
      runtimeDir,
      (message) => onProgress("install-uv", message),
      proxyEnvironment,
    );
  }

  const versionCommand = createOpenFicVersionCommand(venvPythonPath);
  const installedVersion = await readOutput(versionCommand.command, versionCommand.args, runtimeDir);
  const openFicCliPath = resolveOpenFicCliPath(venvPythonPath);
  const openFicCliIsUsable =
    (await pathExists(openFicCliPath)) && (await succeeds(openFicCliPath, ["--help"], runtimeDir));
  if (installedVersion !== expectedVersion || !openFicCliIsUsable) {
    onProgress("install-openfic", installedVersion ? "更新 OpenFic 后端" : "安装 OpenFic 后端");
    const proxyEnvironment = await getSystemProxyEnvironment("https://pypi.org/");
    const installCommand = createOpenFicInstallCommand(
      venvPythonPath,
      expectedVersion,
      installedVersion === expectedVersion && !openFicCliIsUsable,
    );
    await run(
      uvPath,
      installCommand.args,
      runtimeDir,
      (message) => onProgress("install-openfic", message),
      proxyEnvironment,
    );
  }

  return { uvPath, venvPythonPath };
}

const STARTUP_LOG_MILESTONES = [
  {
    text: "Starting OpenFic",
    step: "initialize-backend",
    title: "初始化应用服务",
    message: "正在加载 OpenFic 服务",
    progress: 0.7,
  },
  {
    text: "Database initialization or migration completed",
    step: "initialize-database",
    title: "初始化数据库",
    message: "数据库初始化或迁移已完成",
    progress: 0.82,
  },
  {
    text: "Application startup complete",
    step: "complete-backend-startup",
    title: "完成应用启动",
    message: "应用服务已完成初始化",
    progress: 0.92,
  },
] as const;

export async function startLocalOpenFicBackend(
  venvPythonPath: string,
  expectedVersion: string,
  startupProgress?: StartupProgressTracker,
): Promise<BackendProcessHandle> {
  startupProgress?.begin({
    step: "start-backend",
    title: "启动 OpenFic 服务",
    message: "正在分配本地服务端口",
    progress: 0.6,
  });
  const port = await findFreePort();
  const command = createOpenFicServeCommand(venvPythonPath, port);
  const proxyEnvironment = await getSystemProxyEnvironment("https://pypi.org/");
  let healthFallbackStarted = false;
  let healthFallbackTimer: NodeJS.Timeout | null = null;

  const beginHealthFallback = () => {
    if (healthFallbackStarted) return;
    healthFallbackStarted = true;
    startupProgress?.begin({
      step: "check-health",
      title: "检查服务状态",
      message: "启动阶段停留较久，正在主动检查服务响应",
      progress: 0.96,
    });
  };

  const scheduleHealthFallback = () => {
    if (healthFallbackStarted) return;
    if (healthFallbackTimer) clearTimeout(healthFallbackTimer);
    healthFallbackTimer = setTimeout(beginHealthFallback, 5_000);
  };

  const handle = startBackendProcess({
    command: command.command,
    args: command.args,
    port,
    environment: proxyEnvironment,
    onOutputLine: (line) => {
      if (healthFallbackStarted) return;
      const milestone = STARTUP_LOG_MILESTONES.find((candidate) => line.includes(candidate.text));
      if (!milestone) return;
      startupProgress?.begin(milestone);
      scheduleHealthFallback();
    },
  });

  scheduleHealthFallback();
  try {
    const health = await waitForBackend(handle.baseUrl, { process: handle.process });
    if (healthFallbackTimer) clearTimeout(healthFallbackTimer);
    startupProgress?.begin({
      step: "check-health",
      title: "检查服务状态",
      message: "服务已响应，正在验证版本",
      progress: 0.98,
    });
    if (health.version !== expectedVersion) {
      stopBackendProcess(handle);
      throw new Error(`本地后端版本不匹配：期望 ${expectedVersion}，实际 ${health.version ?? "未知"}`);
    }
    return handle;
  } catch (error) {
    if (healthFallbackTimer) clearTimeout(healthFallbackTimer);
    stopBackendProcess(handle);
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`${message}。日志路径：${handle.logPath}`);
  }
}
