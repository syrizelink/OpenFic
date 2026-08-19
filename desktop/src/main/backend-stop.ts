import type { EventEmitter } from "node:events";

export const BACKEND_GRACEFUL_STOP_TIMEOUT_MS = 10_000;
export const BACKEND_FORCE_STOP_WAIT_MS = 5_000;

export interface BackendStopHandle {
  baseUrl: string;
  process: EventEmitter & {
    killed: boolean;
    exitCode?: number | null;
    signalCode?: NodeJS.Signals | null;
  };
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
  if (!handle) return Promise.resolve();
  if (handle.process.exitCode !== null && handle.process.exitCode !== undefined) return Promise.resolve();
  if (handle.process.signalCode !== null && handle.process.signalCode !== undefined) return Promise.resolve();

  return new Promise((resolve, reject) => {
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
    const fail = () => {
      if (isStopped) return;
      isStopped = true;
      dependencies.cancelFallback(fallback.timeout);
      dependencies.cancelFallback(forced.timeout);
      handle.process.off("exit", finish);
      reject(new Error("backend process did not exit after force stop"));
    };
    const forceStop = () => {
      dependencies.forceStop(handle);
      dependencies.cancelFallback(fallback.timeout);
      if (handle.process.exitCode !== null && handle.process.exitCode !== undefined) {
        finish();
        return;
      }
      if (handle.process.signalCode !== null && handle.process.signalCode !== undefined) {
        finish();
        return;
      }
      forced.timeout = dependencies.scheduleFallback(fail, BACKEND_FORCE_STOP_WAIT_MS);
    };

    handle.process.once("exit", finish);
    fallback.timeout = dependencies.scheduleFallback(forceStop, BACKEND_GRACEFUL_STOP_TIMEOUT_MS);
    void dependencies.requestGracefulShutdown(handle).catch(() => undefined);
  });
}
