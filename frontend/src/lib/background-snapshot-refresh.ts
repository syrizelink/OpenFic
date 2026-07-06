export interface BackgroundSnapshot {
  project_id: string;
  project_revision: number | null;
  summary: {
    statuses: Record<string, unknown>[];
    maintenance: Record<string, unknown>;
  };
}

export interface BackgroundSnapshotRefreshSocket {
  on(event: "background:snapshot", listener: (snapshot: BackgroundSnapshot) => void): void;
  on(
    event: "background:error",
    listener: (payload: { type?: string; reason?: string }) => void,
  ): void;
  off(event: "background:snapshot", listener: (snapshot: BackgroundSnapshot) => void): void;
  off(
    event: "background:error",
    listener: (payload: { type?: string; reason?: string }) => void,
  ): void;
  emit(event: "background:join", payload: { project_id: string }): void;
}

export interface BackgroundSnapshotRefreshTimers {
  timeoutMs?: number;
  setTimeoutFn?: typeof setTimeout;
  clearTimeoutFn?: typeof clearTimeout;
}

export async function joinProjectAndWaitForSnapshot(
  socket: BackgroundSnapshotRefreshSocket,
  projectId: string,
  timers: BackgroundSnapshotRefreshTimers = {},
): Promise<BackgroundSnapshot> {
  const timeoutMs = timers.timeoutMs ?? 5000;
  const setTimeoutFn = timers.setTimeoutFn ?? globalThis.setTimeout;
  const clearTimeoutFn = timers.clearTimeoutFn ?? globalThis.clearTimeout;

  return await new Promise<BackgroundSnapshot>((resolve, reject) => {
    const timeout = setTimeoutFn(() => {
      cleanup();
      reject(new Error("加入后台项目房间超时"));
    }, timeoutMs);

    const cleanup = () => {
      clearTimeoutFn(timeout);
      socket.off("background:snapshot", onSnapshot);
      socket.off("background:error", onError);
    };

    const onSnapshot = (snapshot: BackgroundSnapshot) => {
      if (snapshot.project_id !== projectId) return;
      cleanup();
      resolve(snapshot);
    };

    const onError = (payload: { type?: string; reason?: string }) => {
      if (payload.type !== "invalid_project") return;
      cleanup();
      reject(new Error(payload.reason || "后台事件订阅失败"));
    };

    socket.on("background:snapshot", onSnapshot);
    socket.on("background:error", onError);
    socket.emit("background:join", { project_id: projectId });
  });
}
