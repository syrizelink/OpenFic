import { app, type WebContents } from "electron";
import { stat } from "node:fs/promises";
import { IpcChannels, type SetupProgressEvent } from "../../shared/ipc.js";
import { describeDownloadProgress, ensurePortablePython, inspectPortablePython, resolveRuntimeDir } from "./python.js";
import {
  ensureOpenFicRuntime,
  inspectOpenFicRuntime,
  resolveVenvPythonPath,
  startLocalOpenFicBackend,
} from "./openfic.js";
import type { BackendProcessHandle } from "../process.js";
import type { StartupProgressTracker } from "../startup-progress.js";
import { appendLog, getLogPath } from "../logging.js";
import { throwIfAborted } from "../health.js";

function emitProgress(webContents: WebContents, event: SetupProgressEvent): void {
  webContents.send(IpcChannels.setupProgress, event);
}

const STEP_DONE_MESSAGE: Record<SetupProgressEvent["step"], string> = {
  "download-python": "Python siap",
  "extract-python": "Python telah diekstrak",
  "create-venv": "Runtime telah dibuat",
  "install-uv": "uv telah terpasang",
  "install-openfic": "OpenFic telah terpasang",
};

function markDone(webContents: WebContents, step: SetupProgressEvent["step"]): void {
  emitProgress(webContents, { step, status: "done", message: STEP_DONE_MESSAGE[step] });
}

export async function installLocalRuntime(webContents: WebContents, installDir: string): Promise<string> {
  const runtimeDir = resolveRuntimeDir(installDir);
  let currentStep: SetupProgressEvent["step"] | null = null;

  const beginStep = (step: SetupProgressEvent["step"], message: string) => {
    if (currentStep && currentStep !== step) markDone(webContents, currentStep);
    currentStep = step;
    emitProgress(webContents, { step, status: "running", message });
  };

  appendLog("runtime", `Mulai memasang runtime: ${runtimeDir}`);
  try {
    const python = await ensurePortablePython(
      runtimeDir,
      (phase, message) => beginStep(phase === "download" ? "download-python" : "extract-python", message),
      ({ received, total }) => {
        const fraction = total > 0 ? received / total : undefined;
        emitProgress(webContents, {
          step: "download-python",
          status: "running",
          message: `Mengunduh Python · ${describeDownloadProgress({ received, total })}`,
          progress: fraction,
        });
      },
    );

    await ensureOpenFicRuntime(python, runtimeDir, app.getVersion(), (step, message) => beginStep(step, message));

    if (currentStep) markDone(webContents, currentStep);
    appendLog("runtime", "Pemasangan runtime selesai");
    return runtimeDir;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const logPath = getLogPath("runtime");
    appendLog("runtime", `Pemasangan runtime gagal: ${message}`);
    if (currentStep) emitProgress(webContents, { step: currentStep, status: "failed", message });
    throw new Error(`${message}. Log runtime: ${logPath}`);
  }
}

export interface LocalRuntimeInspection {
  status: "missing" | "incomplete" | "ready";
  message: string;
}

export async function inspectLocalRuntime(installDir: string): Promise<LocalRuntimeInspection> {
  const runtimeDir = resolveRuntimeDir(installDir);
  try {
    if (!(await stat(runtimeDir)).isDirectory()) {
      return { status: "incomplete", message: "Path runtime bukan sebuah direktori" };
    }
  } catch {
    return { status: "missing", message: "Runtime lokal belum terpasang" };
  }

  const python = await inspectPortablePython(runtimeDir);
  if (!python.complete) return { status: "incomplete", message: python.message };

  const openfic = await inspectOpenFicRuntime(runtimeDir, app.getVersion());
  if (!openfic.complete) return { status: "incomplete", message: openfic.message };

  return { status: "ready", message: openfic.message };
}

export async function startLocalBackendFromInstall(
  installDir: string,
  startupProgress?: StartupProgressTracker,
  signal?: AbortSignal,
  dataDir?: string,
): Promise<{ handle: BackendProcessHandle; maintenanceError: string | null }> {
  throwIfAborted(signal);
  const inspection = await inspectLocalRuntime(installDir);
  if (inspection.status !== "ready") {
    throw new Error(`Runtime lokal tidak lengkap: ${inspection.message}. Perbaiki runtime terlebih dahulu.`);
  }
  throwIfAborted(signal);
  const runtimeDir = resolveRuntimeDir(installDir);
  return startLocalOpenFicBackend(resolveVenvPythonPath(runtimeDir), app.getVersion(), startupProgress, signal, dataDir);
}
