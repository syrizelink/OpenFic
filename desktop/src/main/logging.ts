import { app } from "electron";
import { appendFileSync, existsSync, mkdirSync, readFileSync, renameSync, statSync, writeFileSync } from "node:fs";
import { readdir, rename, rm } from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { Writable } from "node:stream";

const MAX_LOG_SIZE_BYTES = 10 * 1024 * 1024;
const UTF8_BOM = Buffer.from([0xef, 0xbb, 0xbf]);

let logsDirOverride: string | null = null;

/** 让日志目录跟随当前活动实例的数据目录；传 null 恢复默认 userData/logs。 */
export function setLogsDir(dataDir: string | null): void {
  logsDirOverride = dataDir;
}

function getLogsDir(): string {
  const logsDir = path.join(logsDirOverride ?? app.getPath("userData"), "logs");
  mkdirSync(logsDir, { recursive: true });
  return logsDir;
}

function normalizeLogName(name: string): string {
  return name.endsWith(".log") ? name : `${name}.log`;
}

function formatLogEntry(message: string): string {
  const lines = message.replace(/\r\n?/g, "\n").split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  const timestamp = new Date().toISOString();
  return (lines.length > 0 ? lines : [""]).map((line) => `[${timestamp}] ${line}\n`).join("");
}

function rotateLogIfNeeded(logPath: string, nextEntrySize: number): void {
  try {
    if (statSync(logPath).size + nextEntrySize <= MAX_LOG_SIZE_BYTES) return;

    const parsed = path.parse(logPath);
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    let suffix = 0;
    let archivedPath = path.join(parsed.dir, `${parsed.name}.${timestamp}${parsed.ext}`);
    while (existsSync(archivedPath)) {
      suffix += 1;
      archivedPath = path.join(parsed.dir, `${parsed.name}.${timestamp}.${suffix}${parsed.ext}`);
    }
    renameSync(logPath, archivedPath);
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") return;
    throw error;
  }
}

function ensureUtf8Bom(logPath: string): void {
  try {
    const content = readFileSync(logPath);
    if (content.subarray(0, UTF8_BOM.length).equals(UTF8_BOM)) return;
    writeFileSync(logPath, Buffer.concat([UTF8_BOM, content]));
  } catch (error) {
    if (!(error instanceof Error) || !("code" in error) || error.code !== "ENOENT") throw error;
    writeFileSync(logPath, UTF8_BOM);
  }
}

export function getLogPath(name: string): string {
  return path.join(getLogsDir(), normalizeLogName(name));
}

export function appendLog(name: string, message: string): void {
  try {
    const entry = formatLogEntry(message);
    const logPath = getLogPath(name);
    rotateLogIfNeeded(logPath, Buffer.byteLength(entry) + UTF8_BOM.length);
    ensureUtf8Bom(logPath);
    appendFileSync(logPath, entry, { encoding: "utf8", flag: "a" });
  } catch {
    // Logging failures must not interrupt the application flow they diagnose.
  }
}

export function createLogStream(name: string): Writable {
  let buffer = "";

  const flush = (value: string) => {
    if (value) appendLog(name, value);
  };

  return new Writable({
    write(chunk, encoding, callback) {
      const text = Buffer.isBuffer(chunk) ? chunk.toString("utf8") : Buffer.from(chunk, encoding).toString("utf8");
      buffer += text.replace(/\r/g, "\n");
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) flush(line);
      callback();
    },
    final(callback) {
      flush(buffer);
      buffer = "";
      callback();
    },
  });
}

function getLogArchiveFileName(): string {
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `openfic-backend-logs-${timestamp}.zip`;
}

function quotePowerShellLiteral(value: string): string {
  return `'${value.replace(/'/g, "''")}'`;
}

function createLogArchive(files: string[], archivePath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const child =
      process.platform === "win32"
        ? spawn(
            "powershell.exe",
            [
              "-NoLogo",
              "-NoProfile",
              "-NonInteractive",
              "-EncodedCommand",
              Buffer.from(
                `$ErrorActionPreference = 'Stop'; Compress-Archive -LiteralPath @(${files.map(quotePowerShellLiteral).join(",")}) -DestinationPath ${quotePowerShellLiteral(archivePath)} -Force`,
                "utf16le",
              ).toString("base64"),
            ],
            { windowsHide: true, stdio: "ignore" },
          )
        : spawn("zip", ["-j", "-q", archivePath, ...files], { stdio: "ignore" });

    child.once("error", reject);
    child.once("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`日志压缩命令退出：${code ?? "未知"}`));
    });
  });
}

export async function exportLogs(destinationPath: string): Promise<string> {
  const logsDir = getLogsDir();
  const files = (await readdir(logsDir, { withFileTypes: true }))
    .filter((entry) => entry.isFile() && entry.name.endsWith(".log"))
    .map((entry) => path.join(logsDir, entry.name));
  if (files.length === 0) throw new Error("暂无可导出的后端日志");

  const temporaryArchivePath = path.join(path.dirname(destinationPath), `.${getLogArchiveFileName()}`);
  appendLog("startup", `开始导出后端日志：${files.length} 个文件`);
  try {
    await createLogArchive(files, temporaryArchivePath);
    await rm(destinationPath, { force: true });
    await rename(temporaryArchivePath, destinationPath);
    appendLog("startup", `后端日志导出完成：${destinationPath}`);
    return destinationPath;
  } catch (error) {
    await rm(temporaryArchivePath, { force: true });
    const message = error instanceof Error ? error.message : String(error);
    appendLog("startup", `后端日志导出失败：${message}`);
    throw new Error(`后端日志导出失败：${message}`);
  }
}
