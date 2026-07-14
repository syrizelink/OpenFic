import { app } from "electron";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createWriteStream, mkdirSync } from "node:fs";
import path from "node:path";

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
  const logsDir = path.join(app.getPath("userData"), "logs");
  mkdirSync(logsDir, { recursive: true });
  return path.join(logsDir, "backend.log");
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
  const logStream = createWriteStream(logPath, { flags: "w" });

  const child = spawn(options.command, options.args, {
    cwd: dataDir,
    env: {
      ...process.env,
      OPENFIC_SERVER_HOST: "127.0.0.1",
      OPENFIC_SERVER_PORT: String(options.port),
      OPENFIC_DATA_DIR: dataDir,
      ...options.environment,
    },
    windowsHide: true,
  });

  child.stdout.pipe(logStream);
  child.stderr.pipe(logStream);
  if (options.onOutputLine) {
    observeOutputLines(child.stdout, options.onOutputLine);
    observeOutputLines(child.stderr, options.onOutputLine);
  }

  return {
    process: child,
    baseUrl: `http://127.0.0.1:${options.port}`,
    logPath,
  };
}

export function stopBackendProcess(handle: BackendProcessHandle | null): void {
  if (!handle || handle.process.killed) return;

  if (process.platform === "win32") {
    spawn("taskkill", ["/F", "/T", "/PID", String(handle.process.pid)], {
      windowsHide: true,
      stdio: "ignore",
    });
    return;
  }

  handle.process.kill("SIGTERM");
}
