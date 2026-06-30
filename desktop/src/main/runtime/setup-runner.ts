import type { WebContents } from "electron";
import { IpcChannels, type SetupProgressEvent } from "../../shared/ipc.js";
import { ensurePortablePython } from "./python.js";
import { ensureOpenFicRuntime, startLocalOpenFicBackend } from "./openfic.js";
import type { BackendProcessHandle } from "../process.js";

function emitProgress(webContents: WebContents, event: SetupProgressEvent): void {
  webContents.send(IpcChannels.setupProgress, event);
}

export async function runLocalSetup(webContents: WebContents): Promise<BackendProcessHandle> {
  const python = await ensurePortablePython((message) =>
    emitProgress(webContents, { step: "download-python", status: "running", message }),
  );
  emitProgress(webContents, { step: "download-python", status: "done", message: "Python 已就绪" });

  const runtime = await ensureOpenFicRuntime(python, (step, message) =>
    emitProgress(webContents, { step, status: "running", message }),
  );
  emitProgress(webContents, { step: "install-openfic", status: "done", message: "OpenFic 已安装" });

  emitProgress(webContents, { step: "start-backend", status: "running", message: "启动 OpenFic 后端" });
  const backend = await startLocalOpenFicBackend(runtime.uvPath);
  emitProgress(webContents, { step: "health-check", status: "done", message: "后端已就绪" });

  return backend;
}
