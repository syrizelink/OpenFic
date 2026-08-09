import type { EventEmitter } from "node:events";

export const BACKEND_GRACEFUL_STOP_TIMEOUT_MS = 10_000;
export const BACKEND_FORCE_STOP_WAIT_MS = 5_000;

export interface BackendStopHandle {
  baseUrl: string;
  process: EventEmitter & { killed: boolean };
  shutdownToken: string;
}

export interface BackendStopDependencies {
  requestGracefulShutdown: (handle: BackendStopHandle) => Promise<void>;
  forceStop: (handle: BackendStopHandle) => void;
  scheduleFallback: (callback: () => void, delayMs: number) => unknown;
  cancelFallback: (timeout: unknown) => void;
}

export function abortBackendStartup(
  handle: BackendStopHandle | null,
  forceStop: (handle: BackendStopHandle) => void,
): void {
  if (!handle || handle.process.killed) return;
  forceStop(handle);
}

export function requestBackendStop(
  handle: BackendStopHandle | null,
  dependencies: BackendStopDependencies,
): Promise<void> {
  if (!handle || handle.process.killed) return Promise.resolve();

  return new Promise((resolve) => {
    let isStopped = false;
    const fallback = { timeout: undefined as unknown };
    const forced = { timeout: undefined as unknown };

    const finish = () => {
      if (isStopped) return;
      isStopped = true;
      dependencies.cancelFallback(fallback.timeout);
      dependencies.cancelFallback(forced.timeout);
      handle.process.off("exit", finish);
      resolve();
    };
    const forceStop = () => {
      dependencies.forceStop(handle);
      dependencies.cancelFallback(fallback.timeout);
      if (handle.process.killed) {
        finish();
        return;
      }
      handle.process.once("exit", finish);
      forced.timeout = dependencies.scheduleFallback(finish, BACKEND_FORCE_STOP_WAIT_MS);
    };

    handle.process.once("exit", finish);
    fallback.timeout = dependencies.scheduleFallback(forceStop, BACKEND_GRACEFUL_STOP_TIMEOUT_MS);
    void dependencies.requestGracefulShutdown(handle).catch(() => undefined);
  });
}
