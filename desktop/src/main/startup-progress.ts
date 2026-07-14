import type { StartupProgressEvent } from "../shared/ipc.js";

type ProgressUpdate = Pick<StartupProgressEvent, "step" | "title" | "message" | "progress">;

export interface StartupProgressTracker {
  begin(update: ProgressUpdate): void;
  update(update: ProgressUpdate): void;
  complete(message?: string): void;
  fail(error: unknown): void;
}

let latestStartupProgress: StartupProgressEvent | null = null;

export function getStartupProgress(): StartupProgressEvent | null {
  return latestStartupProgress;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function createStartupProgressTracker(
  emit: (event: StartupProgressEvent) => void,
): StartupProgressTracker {
  let current: ProgressUpdate | null = null;

  const publish = (event: StartupProgressEvent) => {
    latestStartupProgress = event;
    emit(event);
  };

  const update = (next: ProgressUpdate) => {
    current = next;
    publish({ ...next, status: "running" });
  };

  return {
    begin(next) {
      if (current && current.step !== next.step) {
        publish({ ...current, status: "done" });
      }
      update(next);
    },
    update(next) {
      update(next);
    },
    complete(message) {
      if (!current) return;
      publish({ ...current, message: message ?? current.message, status: "done" });
      current = null;
    },
    fail(error) {
      if (!current) return;
      publish({ ...current, message: errorMessage(error), status: "failed" });
    },
  };
}
