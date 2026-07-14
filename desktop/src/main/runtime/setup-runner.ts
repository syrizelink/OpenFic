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

function emitProgress(webContents: WebContents, event: SetupProgressEvent): void {
  webContents.send(IpcChannels.setupProgress, event);
}

const STEP_DONE_MESSAGE: Record<SetupProgressEvent["step"], string> = {
  "download-python": "Python 已就绪",
  "extract-python": "Python 已解压",
  "create-venv": "运行环境已创建",
  "install-uv": "uv 已安装",
  "install-openfic": "OpenFic 已安装",
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

  const python = await ensurePortablePython(
    runtimeDir,
    (phase, message) => beginStep(phase === "download" ? "download-python" : "extract-python", message),
    ({ received, total }) => {
      const fraction = total > 0 ? received / total : undefined;
      emitProgress(webContents, {
        step: "download-python",
        status: "running",
        message: `下载 Python · ${describeDownloadProgress({ received, total })}`,
        progress: fraction,
      });
    },
  );

  await ensureOpenFicRuntime(python, runtimeDir, app.getVersion(), (step, message) => beginStep(step, message));

  if (currentStep) markDone(webContents, currentStep);

  return runtimeDir;
}

export interface LocalRuntimeInspection {
  status: "missing" | "incomplete" | "ready";
  message: string;
}

export async function inspectLocalRuntime(installDir: string): Promise<LocalRuntimeInspection> {
  const runtimeDir = resolveRuntimeDir(installDir);
  try {
    if (!(await stat(runtimeDir)).isDirectory()) {
      return { status: "incomplete", message: "运行环境路径不是目录" };
    }
  } catch {
    return { status: "missing", message: "尚未安装本地运行环境" };
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
): Promise<BackendProcessHandle> {
  const inspection = await inspectLocalRuntime(installDir);
  if (inspection.status !== "ready") {
    throw new Error(`本地运行环境不完整：${inspection.message}。请先修复运行环境。`);
  }
  const runtimeDir = resolveRuntimeDir(installDir);
  return startLocalOpenFicBackend(resolveVenvPythonPath(runtimeDir), app.getVersion(), startupProgress);
}
