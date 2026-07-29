import { app } from "electron";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { appendLog, createLogStream, getLogPath } from "./logging.js";

export interface BackendProcessHandle {
  process: ChildProcessWithoutNullStreams;
  baseUrl: string;
  logPath: string;
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

  const closeLogs = () => {
    if (logsClosed) return;
    logsClosed = true;
    stdoutLog.end();
    stderrLog.end();
  };

  appendLog("backend", `启动后端命令：${options.command} ${options.args.join(" ")}`);

  const child = spawn(options.command, options.args, {
    cwd: dataDir,
    env: {
      ...process.env,
      OPENFIC_SERVER_HOST: "127.0.0.1",
      OPENFIC_SERVER_PORT: String(options.port),
      OPENFIC_DATA_DIR: dataDir,
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
  };
}

export function stopBackendProcess(handle: BackendProcessHandle | null): void {
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
