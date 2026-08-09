import { net } from "electron";
import { spawn } from "node:child_process";
import { access, mkdir, rm } from "node:fs/promises";
import path from "node:path";
import { findFreePort } from "../ports.js";
import {
  abortStartingBackendProcess,
  startBackendProcess,
  type BackendProcessHandle,
} from "../process.js";
import { configureDefaultSystemProxy, getSystemProxyEnvironment } from "../proxy.js";
import { throwIfAborted, waitForBackend } from "../health.js";
import type { PortablePython, RuntimeIntegrityCheck } from "./python.js";
import {
  createOpenFicInstallCommand,
  createOpenFicServeCommand,
  createOpenFicVersionCommand,
  resolveOpenFicCliPath,
} from "./openfic-commands.js";
import type { StartupProgressTracker } from "../startup-progress.js";
import { appendLog, createLogStream } from "../logging.js";

export type OpenFicRuntimeStep = "create-venv" | "install-uv" | "install-openfic";

const ANSI_ESCAPE_SEQUENCE = new RegExp(`${String.fromCharCode(0x1b)}\\[[0-9;]*[A-Za-z]`, "g");
const DEFAULT_PYPI_INDEX_URL = "https://pypi.org/simple/";
const TSINGHUA_PYPI_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple/";
const PYPI_INDEX_PROBE_TIMEOUT_MS = 5_000;
const PYPI_INDEX_PROBE_PACKAGE = "openfic";
const UTF8_PYTHON_ENVIRONMENT = {
  PYTHONIOENCODING: "utf-8",
  PYTHONUTF8: "1",
};

interface PypiIndexProbe {
  indexUrl: string;
  elapsedMs: number;
}

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
  logStream: NodeJS.WritableStream,
  onLine?: (line: string) => void,
): void {
  if (!stream) return;

  let buffer = "";
  stream.on("data", (chunk: Buffer | string) => {
    const text = typeof chunk === "string" ? chunk : chunk.toString("utf8");
    logStream.write(text);
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
    logStream.end();
  });
}

function stripAnsi(value: string): string {
  return value.replace(ANSI_ESCAPE_SEQUENCE, "");
}

async function probePypiIndex(indexUrl: string, expectedVersion: string): Promise<PypiIndexProbe | null> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), PYPI_INDEX_PROBE_TIMEOUT_MS);
  const startedAt = performance.now();
  try {
    appendLog("runtime", `探测 Python 包索引：${indexUrl}`);
    const response = await net.fetch(`${indexUrl}${PYPI_INDEX_PROBE_PACKAGE}/`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      appendLog("runtime", `Python 包索引响应异常：${indexUrl}，状态码 ${response.status}`);
      return null;
    }
    const packageIndex = await response.text();
    const elapsedMs = performance.now() - startedAt;
    if (!packageIndex.includes(`openfic-${expectedVersion}`)) {
      appendLog("runtime", `Python 包索引未找到 OpenFic ${expectedVersion}：${indexUrl}`);
      return null;
    }
    appendLog("runtime", `Python 包索引可用：${indexUrl}，耗时 ${Math.round(elapsedMs)}ms`);
    return { indexUrl, elapsedMs };
  } catch (error) {
    appendLog("runtime", `Python 包索引探测失败：${indexUrl}：${error instanceof Error ? error.message : String(error)}`);
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

async function getFastestPypiEnvironment(expectedVersion: string): Promise<NodeJS.ProcessEnv> {
  await configureDefaultSystemProxy();
  const probes = await Promise.all(
    [DEFAULT_PYPI_INDEX_URL, TSINGHUA_PYPI_INDEX_URL].map((indexUrl) => probePypiIndex(indexUrl, expectedVersion)),
  );
  let fastestProbe: PypiIndexProbe | null = null;
  for (const probe of probes) {
    if (probe && (!fastestProbe || probe.elapsedMs < fastestProbe.elapsedMs)) fastestProbe = probe;
  }

  const indexUrl = fastestProbe?.indexUrl ?? DEFAULT_PYPI_INDEX_URL;
  appendLog("runtime", `使用 Python 包索引：${indexUrl}`);
  const proxyEnvironment = await getSystemProxyEnvironment(indexUrl);
  return {
    ...proxyEnvironment,
    PIP_INDEX_URL: indexUrl,
    UV_INDEX_URL: indexUrl,
    pip_index_url: indexUrl,
    uv_index_url: indexUrl,
  };
}

function run(
  command: string,
  args: string[],
  cwd: string,
  onOutputLine?: (line: string) => void,
  environment?: NodeJS.ProcessEnv,
): Promise<void> {
  return new Promise((resolve, reject) => {
    appendLog("runtime", `执行命令：${command} ${args.join(" ")}`);
    let lastOutputLine = "";
    const child = spawn(command, args, {
      cwd,
      env: { ...process.env, ...UTF8_PYTHON_ENVIRONMENT, ...environment },
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    const handleOutput = (line: string) => {
      const text = stripAnsi(line).trim();
      if (!text) return;
      lastOutputLine = text;
      onOutputLine?.(text);
    };
    forwardLines(child.stdout, createLogStream("runtime"), handleOutput);
    forwardLines(child.stderr, createLogStream("runtime"), handleOutput);
    child.on("error", (error) => {
      appendLog("runtime", `命令启动失败：${error.message}`);
      reject(error);
    });
    child.on("exit", (code) => {
      if (code === 0) {
        appendLog("runtime", "命令执行完成");
        resolve();
        return;
      }
      const outputDetail = lastOutputLine ? `：${lastOutputLine}` : "";
      const error = new Error(`${command} ${args.join(" ")} exited with code ${code}${outputDetail}`);
      appendLog("runtime", `命令执行失败：${error.message}`);
      reject(error);
    });
  });
}

function readOutput(command: string, args: string[], cwd: string): Promise<string | null> {
  return new Promise((resolve) => {
    appendLog("runtime", `检查命令：${command} ${args.join(" ")}`);
    const child = spawn(command, args, {
      cwd,
      env: { ...process.env, ...UTF8_PYTHON_ENVIRONMENT },
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let output = "";
    const collectOutput = (chunk: Buffer | string) => {
      const text = typeof chunk === "string" ? chunk : chunk.toString("utf8");
      output += text;
    };
    child.stdout.on("data", collectOutput);
    child.stdout.pipe(createLogStream("runtime"));
    child.stderr.pipe(createLogStream("runtime"));
    child.on("error", (error) => {
      appendLog("runtime", `检查命令启动失败：${error.message}`);
      resolve(null);
    });
    child.on("exit", (code) => {
      if (code === 0) {
        appendLog("runtime", "检查命令执行完成");
        resolve(output.trim() || null);
        return;
      }
      appendLog("runtime", `检查命令执行失败：退出码 ${code}`);
      resolve(null);
    });
  });
}

function succeeds(command: string, args: string[], cwd: string): Promise<boolean> {
  return new Promise((resolve) => {
    appendLog("runtime", `检查命令：${command} ${args.join(" ")}`);
    const child = spawn(command, args, {
      cwd,
      env: { ...process.env, ...UTF8_PYTHON_ENVIRONMENT },
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    child.stdout.pipe(createLogStream("runtime"));
    child.stderr.pipe(createLogStream("runtime"));
    child.on("error", (error) => {
      appendLog("runtime", `检查命令启动失败：${error.message}`);
      resolve(false);
    });
    child.on("exit", (code) => {
      appendLog("runtime", code === 0 ? "检查命令执行完成" : `检查命令执行失败：退出码 ${code}`);
      resolve(code === 0);
    });
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
  let pypiEnvironment: Promise<NodeJS.ProcessEnv> | null = null;
  const getPypiEnvironment = () => (pypiEnvironment ??= getFastestPypiEnvironment(expectedVersion));

  appendLog("runtime", `开始检查 OpenFic 运行环境：${runtimeDir}`);
  await mkdir(runtimeDir, { recursive: true });

  if (python.wasReplaced) {
    appendLog("runtime", "便携式 Python 已更新，删除现有虚拟环境");
    await rm(venvDir, { recursive: true, force: true });
  }

  const venvIsUsable =
    (await pathExists(venvPythonPath)) && Boolean(await readOutput(venvPythonPath, ["--version"], runtimeDir));
  if (!venvIsUsable) {
    appendLog("runtime", "虚拟环境不存在或不可用，开始创建");
    await rm(venvDir, { recursive: true, force: true });
    onProgress("create-venv", "创建 OpenFic 运行环境");
    await run(python.pythonPath, ["-m", "venv", venvDir], runtimeDir);
  }

  const uvIsUsable = (await pathExists(uvPath)) && Boolean(await readOutput(uvPath, ["--version"], runtimeDir));
  if (!uvIsUsable) {
    appendLog("runtime", "uv 不存在或不可用，开始安装");
    onProgress("install-uv", "安装 uv");
    const packageIndexEnvironment = await getPypiEnvironment();
    await run(
      venvPythonPath,
      ["-m", "pip", "install", "--force-reinstall", "uv"],
      runtimeDir,
      (message) => onProgress("install-uv", message),
      packageIndexEnvironment,
    );
  }

  const versionCommand = createOpenFicVersionCommand(venvPythonPath);
  const installedVersion = await readOutput(versionCommand.command, versionCommand.args, runtimeDir);
  const openFicCliPath = resolveOpenFicCliPath(venvPythonPath);
  const openFicCliIsUsable =
    (await pathExists(openFicCliPath)) && (await succeeds(openFicCliPath, ["--help"], runtimeDir));
  if (installedVersion !== expectedVersion || !openFicCliIsUsable) {
    appendLog(
      "runtime",
      installedVersion ? `OpenFic 后端需要更新：${installedVersion} -> ${expectedVersion}` : "OpenFic 后端尚未安装",
    );
    onProgress("install-openfic", installedVersion ? "更新 OpenFic 后端" : "安装 OpenFic 后端");
    const packageIndexEnvironment = await getPypiEnvironment();
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
      packageIndexEnvironment,
    );
  }

  appendLog("runtime", "OpenFic 运行环境检查完成");
  return { uvPath, venvPythonPath };
}

const STARTUP_LOG_MILESTONES = [
  {
    text: "Loaded ENCRYPTION_KEY from .key file",
    step: "start-backend",
    title: "启动 OpenFic 服务",
    message: "正在启动服务器进程...",
    progress: 0.64,
  },
  {
    text: "Starting OpenFic",
    step: "initialize-backend",
    title: "启动 OpenFic 服务",
    message: "正在启动 OpenFic 服务...",
    progress: 0.7,
  },
  {
    text: "Database initialization or migration started",
    step: "initialize-database",
    title: "启动 OpenFic 服务",
    message: "正在初始化数据库...",
    progress: 0.76,
  },
  {
    text: "Database initialization or migration completed",
    step: "initialize-database",
    title: "启动 OpenFic 服务",
    message: "已完成数据库初始化及迁移",
    progress: 0.82,
  },
  {
    text: "Background supervisor started",
    step: "complete-backend-startup",
    title: "启动 OpenFic 服务",
    message: "正在启动内部后台任务服务...",
    progress: 0.88,
  },
  {
    text: "Application startup complete",
    step: "complete-backend-startup",
    title: "启动 OpenFic 服务",
    message: "OpenFic 服务已完成初始化",
    progress: 0.92,
  },
] as const;

export async function startLocalOpenFicBackend(
  venvPythonPath: string,
  expectedVersion: string,
  startupProgress?: StartupProgressTracker,
  signal?: AbortSignal,
  dataDir?: string,
): Promise<BackendProcessHandle> {
  throwIfAborted(signal);
  startupProgress?.begin({
    step: "start-backend",
    title: "启动 OpenFic 服务",
    message: "正在分配本地服务端口",
    progress: 0.6,
  });
  const port = await findFreePort();
  throwIfAborted(signal);
  const command = createOpenFicServeCommand(venvPythonPath, port);
  const proxyEnvironment = await getSystemProxyEnvironment("https://pypi.org/");
  throwIfAborted(signal);
  let healthFallbackTimer: NodeJS.Timeout | null = null;
  let latestMilestone: (typeof STARTUP_LOG_MILESTONES)[number] | null = null;

  const beginHealthFallback = () => {
    if (latestMilestone) {
      startupProgress?.update({
        ...latestMilestone,
        message: "启动时间较长，仍在等待应用服务响应",
      });
      return;
    }
    startupProgress?.update({
      step: "start-backend",
      title: "启动 OpenFic 服务",
      message: "启动时间较长，仍在等待应用服务响应",
      progress: 0.6,
    });
  };

  const scheduleHealthFallback = () => {
    if (healthFallbackTimer) clearTimeout(healthFallbackTimer);
    healthFallbackTimer = setTimeout(beginHealthFallback, 5_000);
  };

  const handle = startBackendProcess({
    command: command.command,
    args: command.args,
    port,
    dataDir,
    environment: proxyEnvironment,
    onOutputLine: (line) => {
      const milestone = STARTUP_LOG_MILESTONES.find((candidate) => line.includes(candidate.text));
      if (!milestone) return;
      latestMilestone = milestone;
      startupProgress?.begin(milestone);
      scheduleHealthFallback();
    },
  });

  scheduleHealthFallback();
  try {
    const health = await waitForBackend(handle.baseUrl, { process: handle.process, signal });
    if (healthFallbackTimer) clearTimeout(healthFallbackTimer);
    startupProgress?.begin({
      step: "check-health",
      title: "启动 OpenFic 服务",
      message: "服务已响应，正在验证版本",
      progress: 0.98,
    });
    if (health.version !== expectedVersion) {
      abortStartingBackendProcess(handle);
      throw new Error(`本地后端版本不匹配：期望 ${expectedVersion}，实际 ${health.version ?? "未知"}`);
    }
    return handle;
  } catch (error) {
    if (healthFallbackTimer) clearTimeout(healthFallbackTimer);
    abortStartingBackendProcess(handle);
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`${message}。日志路径：${handle.logPath}`);
  }
}
