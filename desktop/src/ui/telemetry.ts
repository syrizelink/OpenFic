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

/** Menangkap pengecualian tak tertangani pada UI shell desktop (halaman setup/boot/manajemen data), diteruskan ke proses utama lewat IPC untuk dilaporkan. */
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
