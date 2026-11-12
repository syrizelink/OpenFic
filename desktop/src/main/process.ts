import { app } from "electron";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomUUID } from "node:crypto";
import {
  abortBackendStartup,
  requestBackendStop,
  type BackendStopHandle,
} from "./backend-stop.js";
import { appendLog, createLogStream, getLogPath } from "./logging.js";

export interface BackendProcessHandle extends BackendStopHandle {
  process: ChildProcessWithoutNullStreams;
  baseUrl: string;
  logPath: string;
  shutdownToken: string;
  logsClosed: Promise<void>;
  stopPromise?: Promise<void>;
}

export interface StartBackendOptions {
  command: string;
  args: string[];
  port: number;
  dataDir?: string;
  environment?: NodeJS.ProcessEnv;
  onOutputLine?: (line: string) => void;
}

export function getBackendLogPath(): string {
  return getLogPath("backend");
}

function observeOutputLines(stream: NodeJS.ReadableStream, onLine: (line: string) => void): void {
  let buffer = "";
  stream.on("data", (chunk: Buffer | string) => {
    buffer += (typeof chunk === "string" ? chunk : chunk.toString("utf8")).replace(/\r/g, "\n");
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const text = line.trim();
      if (text) onLine(text);
    }
  });
  stream.on("end", () => {
    const text = buffer.trim();
    if (text) onLine(text);
  });
}

export function startBackendProcess(options: StartBackendOptions): BackendProcessHandle {
  const dataDir = options.dataDir ?? app.getPath("userData");
  const logPath = getBackendLogPath();
  const stdoutLog = createLogStream("backend");
  const stderrLog = createLogStream("backend");
  let logsClosed = false;
  let resolveLogsClosed: (() => void) | null = null;
  const logsClosedPromise = new Promise<void>((resolve) => {
    resolveLogsClosed = resolve;
  });
  const shutdownToken = randomUUID();

  const closeLogs = () => {
    if (logsClosed) return;
    logsClosed = true;
    let remaining = 2;
    const markClosed = () => {
      remaining -= 1;
      if (remaining === 0) resolveLogsClosed?.();
    };
    stdoutLog.end(markClosed);
    stderrLog.end(markClosed);
  };

  appendLog("backend", `启动后端命令：${options.command} ${options.args.join(" ")}`);

  const child = spawn(options.command, options.args, {
    cwd: dataDir,
    env: {
      ...process.env,
      OPENFIC_SERVER_HOST: "127.0.0.1",
      OPENFIC_SERVER_PORT: String(options.port),
      OPENFIC_DATA_DIR: dataDir,
      OPENFIC_SHUTDOWN_TOKEN: shutdownToken,
      PYTHONIOENCODING: "utf-8",
      PYTHONUTF8: "1",
      ...options.environment,
    },
    windowsHide: true,
  });

  child.stdout.pipe(stdoutLog, { end: false });
  child.stderr.pipe(stderrLog, { end: false });
  if (options.onOutputLine) {
    observeOutputLines(child.stdout, options.onOutputLine);
    observeOutputLines(child.stderr, options.onOutputLine);
  }
  child.once("error", (error) => {
    appendLog("backend", `后端进程启动失败：${error.message}`);
    closeLogs();
  });
  child.once("close", (code, signal) => {
    appendLog("backend", `后端进程已退出：code=${code ?? "null"} signal=${signal ?? "none"}`);
    closeLogs();
  });

  return {
    process: child,
    baseUrl: `http://127.0.0.1:${options.port}`,
    logPath,
    shutdownToken,
    logsClosed: logsClosedPromise,
  };
}

export function forceStopBackendProcess(handle: BackendProcessHandle | null): void {
  if (!handle || handle.process.killed) return;

  appendLog("backend", `请求停止后端进程：pid=${handle.process.pid ?? "unknown"}`);

  if (process.platform === "win32") {
    spawn("taskkill", ["/F", "/T", "/PID", String(handle.process.pid)], {
      windowsHide: true,
      stdio: "ignore",
    });
    return;
  }

  handle.process.kill("SIGTERM");
}

export function abortStartingBackendProcess(handle: BackendProcessHandle | null): void {
  abortBackendStartup(handle, (startingHandle) =>
    forceStopBackendProcess(startingHandle as BackendProcessHandle),
  );
}

async function requestGracefulBackendShutdown(handle: BackendStopHandle): Promise<void> {
  const response = await fetch(`${handle.baseUrl}/api/v1/health/shutdown`, {
    method: "POST",
    headers: { "X-OpenFic-Shutdown-Token": handle.shutdownToken },
  });
  if (!response.ok) throw new Error(`graceful backend shutdown rejected: ${response.status}`);
}

export function stopBackendProcess(handle: BackendProcessHandle | null): Promise<void> {
  if (!handle) return Promise.resolve();
  if (handle.stopPromise) return handle.stopPromise;

  appendLog("backend", `请求优雅停止后端进程：pid=${handle.process.pid ?? "unknown"}`);
  handle.stopPromise = requestBackendStop(handle, {
    requestGracefulShutdown: requestGracefulBackendShutdown,
    forceStop: (stopHandle) => forceStopBackendProcess(stopHandle as BackendProcessHandle),
    scheduleFallback: (callback, delayMs) => setTimeout(callback, delayMs),
    cancelFallback: (timeout) => clearTimeout(timeout as NodeJS.Timeout),
  }).then(() => Promise.race([
    handle.logsClosed,
    new Promise<void>((resolve) => setTimeout(resolve, 1_000)),
  ]));
  return handle.stopPromise;
}
