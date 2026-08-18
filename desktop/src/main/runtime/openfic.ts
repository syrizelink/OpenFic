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
import type { StartupProgressTracker, ProgressUpdate } from "../startup-progress.js";
import { appendLog, createLogStream } from "../logging.js";

export type OpenFicRuntimeStep = "create-venv" | "install-uv" | "install-openfic";

const ANSI_ESCAPE_SEQUENCE = new RegExp(`${String.fromCharCode(0x1b)}\\[[0-9;]*[A-Za-z]`, "g");
const DEFAULT_PYPI_INDEX_URL = "https://pypi.org/simple/";
const TSINGHUA_PYPI_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple/";
const PYPI_INDEX_PROBE_TIMEOUT_MS = 5_000;
const BACKEND_READY_TIMEOUT_MS = 60 * 60_000;
const PYPI_INDEX_PROBE_PACKAGE = "openfic";
const UV_SYSTEM_CERTS_HINT = "Consider enabling use of system TLS certificates";
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

async function buildPypiEnvironment(indexUrl: string): Promise<NodeJS.ProcessEnv> {
  const proxyEnvironment = await getSystemProxyEnvironment(indexUrl);
  return {
    ...proxyEnvironment,
    PIP_INDEX_URL: indexUrl,
    UV_INDEX_URL: indexUrl,
    pip_index_url: indexUrl,
    uv_index_url: indexUrl,
  };
}

async function getPypiEnvironmentsBySpeed(expectedVersion: string): Promise<NodeJS.ProcessEnv[]> {
  await configureDefaultSystemProxy();
  const probes = await Promise.all(
    [DEFAULT_PYPI_INDEX_URL, TSINGHUA_PYPI_INDEX_URL].map((indexUrl) => probePypiIndex(indexUrl, expectedVersion)),
  );
  const orderedUrls = probes
    .filter((probe): probe is PypiIndexProbe => probe !== null)
    .sort((a, b) => a.elapsedMs - b.elapsedMs)
    .map((probe) => probe.indexUrl);
  if (orderedUrls.length === 0) orderedUrls.push(DEFAULT_PYPI_INDEX_URL);

  appendLog("runtime", `Python 包索引回退顺序：${orderedUrls.join(", ")}`);
  return Promise.all(orderedUrls.map((indexUrl) => buildPypiEnvironment(indexUrl)));
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
    const outputLines: string[] = [];
    const child = spawn(command, args, {
      cwd,
      env: { ...process.env, ...UTF8_PYTHON_ENVIRONMENT, ...environment },
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    const handleOutput = (line: string) => {
      const text = stripAnsi(line).trim();
      if (!text) return;
      outputLines.push(text);
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
      const outputDetail = outputLines.length ? `：${outputLines.join("\n")}` : "";
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

async function runUvInstallWithSystemCertsRetry(
  uvPath: string,
  args: string[],
  cwd: string,
  onProgress: (step: OpenFicRuntimeStep, message: string) => void,
  environment?: NodeJS.ProcessEnv,
): Promise<void> {
  try {
    await run(uvPath, args, cwd, (line) => onProgress("install-openfic", line), environment);
  } catch (error) {
    if (error instanceof Error && error.message.includes(UV_SYSTEM_CERTS_HINT)) {
      appendLog("runtime", "检测到 TLS 证书错误，使用 --system-certs 重试");
      await run(
        uvPath,
        ["--system-certs", ...args],
        cwd,
        (line) => onProgress("install-openfic", line),
        environment,
      );
      return;
    }
    throw error;
  }
}

async function runInstallWithIndexFallback(
  environments: NodeJS.ProcessEnv[],
  runInstall: (environment: NodeJS.ProcessEnv) => Promise<void>,
): Promise<void> {
  let lastError: unknown = null;
  for (let index = 0; index < environments.length; index += 1) {
    const environment = environments[index];
    const indexUrl = environment.UV_INDEX_URL ?? environment.PIP_INDEX_URL ?? `第 ${index + 1} 个`;
    appendLog("runtime", `尝试使用 Python 包索引安装：${indexUrl}`);
    try {
      await runInstall(environment);
      return;
    } catch (error) {
      lastError = error;
      appendLog("runtime", `使用 ${indexUrl} 安装失败，尝试回退：${error instanceof Error ? error.message : String(error)}`);
    }
  }
  throw lastError;
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
  let pypiEnvironments: Promise<NodeJS.ProcessEnv[]> | null = null;
  const getPypiEnvironments = () => (pypiEnvironments ??= getPypiEnvironmentsBySpeed(expectedVersion));

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
    const packageIndexEnvironments = await getPypiEnvironments();
    await runInstallWithIndexFallback(packageIndexEnvironments, (environment) =>
      run(
        venvPythonPath,
        ["-m", "pip", "install", "--force-reinstall", "uv"],
        runtimeDir,
        (message) => onProgress("install-uv", message),
        environment,
      ),
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
    const packageIndexEnvironments = await getPypiEnvironments();
    const installCommand = createOpenFicInstallCommand(
      venvPythonPath,
      expectedVersion,
      installedVersion === expectedVersion && !openFicCliIsUsable,
    );
    await runInstallWithIndexFallback(packageIndexEnvironments, (environment) =>
      runUvInstallWithSystemCertsRetry(uvPath, installCommand.args, runtimeDir, onProgress, environment),
    );
  }

  appendLog("runtime", "OpenFic 运行环境检查完成");
  return { uvPath, venvPythonPath };
}

const STARTUP_TITLE = "启动 OpenFic 服务";

type StartupLogProgress = Omit<ProgressUpdate, "title">;

interface StartupLogRule {
  match: RegExp;
  toProgress: (captures: RegExpMatchArray) => StartupLogProgress;
}

// 规则顺序与后端真实日志时序一致（见 backend/app/main.py lifespan）。
// 进度单调递增：0.64 → 0.70 → 0.76 → 0.82 → 维护(0.83→0.94) → 0.95 → 0.96 → health(0.98) → ready(1.0)
const STARTUP_LOG_RULES: StartupLogRule[] = [
  {
    match: /Loaded ENCRYPTION_KEY from \.key file/,
    toProgress: () => ({
      step: "start-backend",
      message: "正在启动服务器进程...",
      progress: 0.64,
    }),
  },
  {
    match: /Starting OpenFic/,
    toProgress: () => ({
      step: "initialize-backend",
      message: "正在启动 OpenFic 服务...",
      progress: 0.7,
    }),
  },
  {
    match: /Database initialization or migration started/,
    toProgress: () => ({
      step: "initialize-database",
      message: "正在初始化数据库...",
      progress: 0.76,
    }),
  },
  {
    match: /Database initialization or migration completed/,
    toProgress: () => ({
      step: "initialize-database",
      message: "已完成数据库初始化及迁移",
      progress: 0.82,
    }),
  },
  // 维护开始（loguru 行，带换行实时到达）
  {
    match: /Local database maintenance started/,
    toProgress: () => ({
      step: "maintain-database",
      message: "正在清理和压缩本地数据",
      progress: 0.83,
      indeterminate: true,
      maintenancePhase: "pruning",
      maintenanceProgress: null,
    }),
  },
  // 阶段 1 迁移开始（loguru 行）
  {
    match: /Migrating checkpoint database to incremental auto-vacuum/,
    toProgress: () => ({
      step: "maintain-database",
      message: "正在迁移检查点数据库",
      progress: 0.84,
      indeterminate: true,
      maintenancePhase: "migrating",
      maintenanceProgress: null,
    }),
  },
  // 阶段 1 迁移完成（loguru 行）
  {
    match: /Migrated checkpoint database to incremental auto-vacuum/,
    toProgress: () => ({
      step: "maintain-database",
      message: "检查点数据库迁移完成",
      progress: 0.86,
      maintenancePhase: "migrating",
      maintenanceProgress: 1,
    }),
  },
  // 阶段 2 回收开始（loguru 行）
  {
    match: /Reclaiming checkpoint free space:/,
    toProgress: () => ({
      step: "maintain-database",
      message: "正在清理和压缩本地数据",
      progress: 0.88,
      maintenancePhase: "vacuuming",
      maintenanceProgress: 0,
    }),
  },
  // 阶段 2 跳过回收（loguru 行）
  {
    match: /Checkpoint free space below threshold, skipping vacuum/,
    toProgress: () => ({
      step: "maintain-database",
      message: "数据库空间充足，跳过压缩",
      progress: 0.9,
      maintenancePhase: "vacuuming",
      maintenanceProgress: 1,
    }),
  },
  // 维护的最后一步（start_background_runtime 在 _run_startup_maintenance 内被调用）
  {
    match: /Background supervisor started/,
    toProgress: () => ({
      step: "complete-backend-startup",
      message: "正在启动内部后台任务服务...",
      progress: 0.95,
    }),
  },
  // 维护完成（loguru 行）
  {
    match: /Local database maintenance completed/,
    toProgress: () => ({
      step: "complete-backend-startup",
      message: "本地数据库维护完成",
      progress: 0.96,
    }),
  },
  // lifespan 完成，服务可访问
  {
    match: /Application startup complete/,
    toProgress: () => ({
      step: "complete-backend-startup",
      message: "OpenFic 服务已完成初始化",
      progress: 0.97,
    }),
  },
  // [maintenance] 进度行：\r 无换行，实际由后续 \r 冲刷送达，作为上述 loguru 步骤的进度补充
  {
    match: /\[maintenance\] Migrating checkpoint database: ([\d,]+) VM ops, ([\d.]+)s elapsed/,
    toProgress: (captures) => ({
      step: "maintain-database",
      message: "正在迁移检查点数据库",
      progress: 0.84,
      indeterminate: true,
      maintenancePhase: "migrating",
      maintenanceProgress: null,
      maintenanceVmOps: Number(captures[1].replace(/,/g, "")),
      maintenanceElapsedSeconds: Number(captures[2]),
    }),
  },
  {
    match: /\[maintenance\] Compacting checkpoint database: ([\d.]+)\/([\d.]+)GB \(([\d.]+)%\)/,
    toProgress: (captures) => {
      const reclaimed = Number(captures[1]);
      const total = Number(captures[2]);
      const percent = Number(captures[3]);
      return {
        step: "maintain-database",
        message: "正在清理和压缩本地数据",
        progress: 0.88 + (Math.min(100, Math.max(0, percent)) / 100) * 0.06,
        maintenancePhase: "vacuuming",
        maintenanceProgress: percent / 100,
        maintenanceReclaimedBytes: reclaimed * 1024 ** 3,
        maintenanceTotalBytes: total * 1024 ** 3,
      };
    },
  },
];

function matchStartupLogLine(line: string): ProgressUpdate | null {
  for (const rule of STARTUP_LOG_RULES) {
    const captures = line.match(rule.match);
    if (!captures) continue;
    return { title: STARTUP_TITLE, ...rule.toProgress(captures) };
  }
  return null;
}

export async function startLocalOpenFicBackend(
  venvPythonPath: string,
  expectedVersion: string,
  startupProgress?: StartupProgressTracker,
  signal?: AbortSignal,
  dataDir?: string,
): Promise<{ handle: BackendProcessHandle; maintenanceError: string | null }> {
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
  let latestMilestone: ProgressUpdate | null = null;

  const handle = startBackendProcess({
    command: command.command,
    args: command.args,
    port,
    dataDir,
    environment: proxyEnvironment,
    onOutputLine: (line) => {
      const progress = matchStartupLogLine(line);
      if (!progress) return;
      // 日志时序可能与规则表顺序不一致（如维护行之后才输出启动完成行），
      // 进度只允许单调递增，忽略会回退的匹配，保证 UI 进度不倒退。
      if (progress.progress < (latestMilestone?.progress ?? 0)) return;
      latestMilestone = progress;
      startupProgress?.begin(progress);
    },
  });

  try {
    const health = await waitForBackend(handle.baseUrl, {
      process: handle.process,
      signal,
      timeoutMs: BACKEND_READY_TIMEOUT_MS,
    });
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

    const maintenanceError = await fetchBackendMaintenanceError(handle.baseUrl);

    return { handle, maintenanceError };
  } catch (error) {
    abortStartingBackendProcess(handle);
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`${message}。日志路径：${handle.logPath}`);
  }
}

async function fetchBackendMaintenanceError(baseUrl: string): Promise<string | null> {
  try {
    const response = await fetch(`${baseUrl}/api/v1/health/maintenance`);
    if (!response.ok) return null;
    const data = (await response.json()) as { status?: string; error?: string | null };
    if (data.status !== "failed") return null;
    return data.error || "本地数据库维护失败";
  } catch {
    return null;
  }
}
