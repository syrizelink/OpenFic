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
}

export function getBackendLogPath(): string {
  const logsDir = path.join(app.getPath("userData"), "logs");
  mkdirSync(logsDir, { recursive: true });
  return path.join(logsDir, "backend.log");
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
    },
    windowsHide: true,
  });

  child.stdout.pipe(logStream);
  child.stderr.pipe(logStream);

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
