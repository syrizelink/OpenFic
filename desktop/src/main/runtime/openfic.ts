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
    appendLog("runtime", `Menyelidiki indeks paket Python: ${indexUrl}`);
    const response = await net.fetch(`${indexUrl}${PYPI_INDEX_PROBE_PACKAGE}/`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      appendLog("runtime", `Respons indeks paket Python tidak normal: ${indexUrl}, kode status ${response.status}`);
      return null;
    }
    const packageIndex = await response.text();
    const elapsedMs = performance.now() - startedAt;
    if (!packageIndex.includes(`openfic-${expectedVersion}`)) {
      appendLog("runtime", `Indeks paket Python tidak memiliki OpenFic ${expectedVersion}: ${indexUrl}`);
      return null;
    }
    appendLog("runtime", `Indeks paket Python tersedia: ${indexUrl}, memakan waktu ${Math.round(elapsedMs)}ms`);
    return { indexUrl, elapsedMs };
  } catch (error) {
    appendLog("runtime", `Penyelidikan indeks paket Python gagal: ${indexUrl}: ${error instanceof Error ? error.message : String(error)}`);
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

  appendLog("runtime", `Urutan fallback indeks paket Python: ${orderedUrls.join(", ")}`);
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
    appendLog("runtime", `Menjalankan perintah: ${command} ${args.join(" ")}`);
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
      appendLog("runtime", `Perintah gagal dijalankan: ${error.message}`);
      reject(error);
    });
    child.on("exit", (code) => {
      if (code === 0) {
        appendLog("runtime", "Perintah selesai dijalankan");
        resolve();
        return;
      }
      const outputDetail = outputLines.length ? `: ${outputLines.join("\n")}` : "";
      const error = new Error(`${command} ${args.join(" ")} exited with code ${code}${outputDetail}`);
      appendLog("runtime", `Perintah gagal dijalankan: ${error.message}`);
      reject(error);
    });
  });
}

function readOutput(command: string, args: string[], cwd: string): Promise<string | null> {
  return new Promise((resolve) => {
    appendLog("runtime", `Perintah pemeriksaan: ${command} ${args.join(" ")}`);
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
      appendLog("runtime", `Perintah pemeriksaan gagal dijalankan: ${error.message}`);
      resolve(null);
    });
    child.on("exit", (code) => {
      if (code === 0) {
        appendLog("runtime", "Perintah pemeriksaan selesai dijalankan");
        resolve(output.trim() || null);
        return;
      }
      appendLog("runtime", `Perintah pemeriksaan gagal: kode keluar ${code}`);
      resolve(null);
    });
  });
}

function succeeds(command: string, args: string[], cwd: string): Promise<boolean> {
  return new Promise((resolve) => {
    appendLog("runtime", `Perintah pemeriksaan: ${command} ${args.join(" ")}`);
    const child = spawn(command, args, {
      cwd,
      env: { ...process.env, ...UTF8_PYTHON_ENVIRONMENT },
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    child.stdout.pipe(createLogStream("runtime"));
    child.stderr.pipe(createLogStream("runtime"));
    child.on("error", (error) => {
      appendLog("runtime", `Perintah pemeriksaan gagal dijalankan: ${error.message}`);
      resolve(false);
    });
    child.on("exit", (code) => {
      appendLog("runtime", code === 0 ? "Perintah pemeriksaan selesai dijalankan" : `Perintah pemeriksaan gagal: kode keluar ${code}`);
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
      appendLog("runtime", "Galat sertifikat TLS terdeteksi, mencoba ulang dengan --system-certs");
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
    const indexUrl = environment.UV_INDEX_URL ?? environment.PIP_INDEX_URL ?? `ke-${index + 1}`;
    appendLog("runtime", `Mencoba memasang lewat indeks paket Python: ${indexUrl}`);
    try {
      await runInstall(environment);
      return;
    } catch (error) {
      lastError = error;
      appendLog("runtime", `Pemasangan lewat ${indexUrl} gagal, mencoba fallback: ${error instanceof Error ? error.message : String(error)}`);
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
    return { complete: false, message: "Virtual environment Python tidak ditemukan" };
  }
  if (!(await readOutput(venvPythonPath, ["--version"], runtimeDir))) {
    return { complete: false, message: "Virtual environment Python tidak tersedia" };
  }

  const uvPath = getUvPath(runtimeDir);
  if (!(await pathExists(uvPath)) || !(await readOutput(uvPath, ["--version"], runtimeDir))) {
    return { complete: false, message: "uv tidak ada atau tidak tersedia" };
  }

  const versionCommand = createOpenFicVersionCommand(venvPythonPath);
  const installedVersion = await readOutput(versionCommand.command, versionCommand.args, runtimeDir);
  if (installedVersion !== expectedVersion) {
    return {
      complete: false,
      message: installedVersion ? "Versi backend OpenFic tidak cocok" : "Backend OpenFic tidak ditemukan",
    };
  }
  const openFicCliPath = resolveOpenFicCliPath(venvPythonPath);
  if (!(await pathExists(openFicCliPath)) || !(await succeeds(openFicCliPath, ["--help"], runtimeDir))) {
    return { complete: false, message: "Program baris perintah OpenFic hilang atau tidak tersedia" };
  }

  return { complete: true, message: "Runtime OpenFic telah terpasang lengkap" };
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

  appendLog("runtime", `Mulai memeriksa runtime OpenFic: ${runtimeDir}`);
  await mkdir(runtimeDir, { recursive: true });

  if (python.wasReplaced) {
    appendLog("runtime", "Python portabel telah diperbarui, menghapus virtual environment yang ada");
    await rm(venvDir, { recursive: true, force: true });
  }

  const venvIsUsable =
    (await pathExists(venvPythonPath)) && Boolean(await readOutput(venvPythonPath, ["--version"], runtimeDir));
  if (!venvIsUsable) {
    appendLog("runtime", "Virtual environment tidak ada atau tidak tersedia, mulai membuat");
    await rm(venvDir, { recursive: true, force: true });
    onProgress("create-venv", "Membuat runtime OpenFic");
    await run(python.pythonPath, ["-m", "venv", venvDir], runtimeDir);
  }

  const uvIsUsable = (await pathExists(uvPath)) && Boolean(await readOutput(uvPath, ["--version"], runtimeDir));
  if (!uvIsUsable) {
    appendLog("runtime", "uv tidak ada atau tidak tersedia, mulai memasang");
    onProgress("install-uv", "Memasang uv");
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
      installedVersion ? `Backend OpenFic perlu diperbarui: ${installedVersion} -> ${expectedVersion}` : "Backend OpenFic belum terpasang",
    );
    onProgress("install-openfic", installedVersion ? "Memperbarui backend OpenFic" : "Memasang backend OpenFic");
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

  appendLog("runtime", "Pemeriksaan runtime OpenFic selesai");
  return { uvPath, venvPythonPath };
}

const STARTUP_TITLE = "Menjalankan layanan OpenFic";

type StartupLogProgress = Omit<ProgressUpdate, "title">;

interface StartupLogRule {
  match: RegExp;
  toProgress: (captures: RegExpMatchArray) => StartupLogProgress;
}

// Urutan aturan mengikuti urutan waktu log backend yang sebenarnya (lihat lifespan di backend/app/main.py).
// Progres naik secara monoton: 0.64 -> 0.70 -> 0.76 -> 0.82 -> perawatan (0.83->0.94) -> 0.95 -> 0.96 -> health (0.98) -> ready (1.0)
const STARTUP_LOG_RULES: StartupLogRule[] = [
  {
    match: /Loaded ENCRYPTION_KEY from \.key file/,
    toProgress: () => ({
      step: "start-backend",
      message: "Menjalankan proses server...",
      progress: 0.64,
    }),
  },
  {
    match: /Starting OpenFic/,
    toProgress: () => ({
      step: "initialize-backend",
      message: "Menjalankan layanan OpenFic...",
      progress: 0.7,
    }),
  },
  {
    match: /Database initialization or migration started/,
    toProgress: () => ({
      step: "initialize-database",
      message: "Menginisialisasi basis data...",
      progress: 0.76,
    }),
  },
  {
    match: /Database initialization or migration completed/,
    toProgress: () => ({
      step: "initialize-database",
      message: "Inisialisasi dan migrasi basis data selesai",
      progress: 0.82,
    }),
  },
  // Perawatan dimulai (baris loguru, tiba secara langsung dengan newline)
  {
    match: /Local database maintenance started/,
    toProgress: () => ({
      step: "maintain-database",
      message: "Membersihkan dan memadatkan data lokal",
      progress: 0.83,
      indeterminate: true,
      maintenancePhase: "pruning",
      maintenanceProgress: null,
    }),
  },
  // Migrasi tahap 1 dimulai (baris loguru)
  {
    match: /Migrating checkpoint database to incremental auto-vacuum/,
    toProgress: () => ({
      step: "maintain-database",
      message: "Memigrasikan basis data checkpoint",
      progress: 0.84,
      indeterminate: true,
      maintenancePhase: "migrating",
      maintenanceProgress: null,
    }),
  },
  // Migrasi tahap 1 selesai (baris loguru)
  {
    match: /Migrated checkpoint database to incremental auto-vacuum/,
    toProgress: () => ({
      step: "maintain-database",
      message: "Migrasi basis data checkpoint selesai",
      progress: 0.86,
      maintenancePhase: "migrating",
      maintenanceProgress: 1,
    }),
  },
  // Reklamasi tahap 2 dimulai (baris loguru)
  {
    match: /Reclaiming checkpoint free space:/,
    toProgress: () => ({
      step: "maintain-database",
      message: "Membersihkan dan memadatkan data lokal",
      progress: 0.88,
      maintenancePhase: "vacuuming",
      maintenanceProgress: 0,
    }),
  },
  // Reklamasi tahap 2 dilewati (baris loguru)
  {
    match: /Checkpoint free space below threshold, skipping vacuum/,
    toProgress: () => ({
      step: "maintain-database",
      message: "Ruang basis data mencukupi, pemadatan dilewati",
      progress: 0.9,
      maintenancePhase: "vacuuming",
      maintenanceProgress: 1,
    }),
  },
  // Langkah terakhir perawatan (start_background_runtime dipanggil di dalam _run_startup_maintenance)
  {
    match: /Background supervisor started/,
    toProgress: () => ({
      step: "complete-backend-startup",
      message: "Menjalankan layanan tugas latar belakang internal...",
      progress: 0.95,
    }),
  },
  // Perawatan selesai (baris loguru)
  {
    match: /Local database maintenance completed/,
    toProgress: () => ({
      step: "complete-backend-startup",
      message: "Perawatan basis data lokal selesai",
      progress: 0.96,
    }),
  },
  // lifespan selesai, layanan dapat diakses
  {
    match: /Application startup complete/,
    toProgress: () => ({
      step: "complete-backend-startup",
      message: "Inisialisasi layanan OpenFic selesai",
      progress: 0.97,
    }),
  },
  // Baris progres [maintenance]: \r tanpa newline, sebenarnya dikirim oleh flush \r berikutnya, sebagai pelengkap progres langkah loguru di atas
  {
    match: /\[maintenance\] Migrating checkpoint database: ([\d,]+) VM ops, ([\d.]+)s elapsed/,
    toProgress: (captures) => ({
      step: "maintain-database",
      message: "Memigrasikan basis data checkpoint",
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
        message: "Membersihkan dan memadatkan data lokal",
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
    title: "Menjalankan layanan OpenFic",
    message: "Mengalokasikan port layanan lokal",
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
      // Urutan waktu log bisa berbeda dari urutan tabel aturan (misalnya baris selesai menjalankan baru muncul setelah baris perawatan),
      // progres hanya boleh naik monoton; kecocokan yang menurunkan progres diabaikan agar progres UI tidak mundur.
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
      title: "Menjalankan layanan OpenFic",
      message: "Layanan merespons, sedang memverifikasi versi",
      progress: 0.98,
    });
    if (health.version !== expectedVersion) {
      abortStartingBackendProcess(handle);
      throw new Error(`Versi backend lokal tidak cocok: diharapkan ${expectedVersion}, aktual ${health.version ?? "tidak diketahui"}`);
    }

    const maintenanceError = await fetchBackendMaintenanceError(handle.baseUrl);

    return { handle, maintenanceError };
  } catch (error) {
    abortStartingBackendProcess(handle);
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`${message}. Path log: ${handle.logPath}`);
  }
}

async function fetchBackendMaintenanceError(baseUrl: string): Promise<string | null> {
  try {
    const response = await fetch(`${baseUrl}/api/v1/health/maintenance`);
    if (!response.ok) return null;
    const data = (await response.json()) as { status?: string; error?: string | null };
    if (data.status !== "failed") return null;
    return data.error || "Perawatan basis data lokal gagal";
  } catch {
    return null;
  }
}
