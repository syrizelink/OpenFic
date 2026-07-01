import type { WebContents } from "electron";
import { IpcChannels, type SetupProgressEvent } from "../../shared/ipc.js";
import { describeDownloadProgress, ensurePortablePython, resolveRuntimeDir } from "./python.js";
import { ensureOpenFicRuntime, resolveUvPath, resolveVenvPythonPath, startLocalOpenFicBackend } from "./openfic.js";
import type { BackendProcessHandle } from "../process.js";

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

  await ensureOpenFicRuntime(python, runtimeDir, (step, message) => beginStep(step, message));

  if (currentStep) markDone(webContents, currentStep);

  return runtimeDir;
}

export async function startLocalBackendFromInstall(installDir: string): Promise<BackendProcessHandle> {
  const runtimeDir = resolveRuntimeDir(installDir);
  return startLocalOpenFicBackend(resolveUvPath(runtimeDir), resolveVenvPythonPath(runtimeDir));
}
