import type { ReportErrorPayload } from "../shared/ipc";

function serializeError(error: unknown): ReportErrorPayload | null {
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message.slice(0, 2000),
      stack: error.stack?.slice(0, 5000),
    };
  }
  if (typeof error === "string" && error) {
    return { name: "Error", message: error.slice(0, 2000) };
  }
  return null;
}

/** 捕获桌面外壳 UI（setup/boot/数据管理页）的未处理异常，经 IPC 转发给主进程上报。 */
export function installShellErrorTelemetry(): void {
  window.addEventListener("error", (event) => {
    const payload = serializeError(event.error ?? event.message);
    if (payload) window.openficDesktop.reportError(payload);
  });

  window.addEventListener("unhandledrejection", (event) => {
    const payload = serializeError(event.reason);
    if (payload) window.openficDesktop.reportError(payload);
  });
}
