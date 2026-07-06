import type { Socket } from "socket.io-client";

import {
  joinProjectAndWaitForSnapshot,
  type BackgroundSnapshot,
} from "./background-snapshot-refresh";
import { connectSocket, getSocket } from "./socket-client";

export type { BackgroundSnapshot } from "./background-snapshot-refresh";

export interface BackgroundEvent {
  type: string;
  job_type: string;
  job_id?: string;
  item_id?: string | null;
  item_type?: string | null;
  project_id?: string | null;
  subject_type?: string | null;
  subject_id?: string | null;
  task_id?: string | null;
  chapter_id?: string | null;
  agent_session_id?: string | null;
  is_running?: boolean | null;
  title?: string | null;
  updated_at?: string | null;
  payload?: Record<string, unknown>;
  created_at?: string;
  project_revision?: number | null;
}

export interface BackgroundEventSubscription {
  close(): void;
}

export type BackgroundProjectionSubscription = BackgroundEventSubscription;

type BackgroundSnapshotListener = (snapshot: BackgroundSnapshot) => void;
type BackgroundListener = (event: BackgroundEvent) => void;
type ErrorListener = (error: Error) => void;
type IndexStatusListener = (status: Record<string, unknown> | undefined) => void;
type IndexConfigListener = () => void;

const projectSnapshotListeners = new Map<string, Set<BackgroundSnapshotListener>>();
const projectEventListeners = new Map<string, Set<BackgroundListener>>();
const projectIndexStatusListeners = new Map<string, Set<IndexStatusListener>>();
const indexConfigListeners = new Set<IndexConfigListener>();
const errorListeners = new Set<ErrorListener>();
const projectRefCounts = new Map<string, number>();
const pendingJoins = new Set<string>();
const joinedProjects = new Set<string>();
const leaveAfterJoinProjects = new Set<string>();
const joinAttemptIds = new Map<string, number>();

let handlersBound = false;
let boundSocket: Socket | null = null;

function nextJoinAttempt(projectId: string): number {
  const nextAttempt = (joinAttemptIds.get(projectId) ?? 0) + 1;
  joinAttemptIds.set(projectId, nextAttempt);
  return nextAttempt;
}

function currentJoinAttempt(projectId: string): number {
  return joinAttemptIds.get(projectId) ?? 0;
}

function handleConnect() {
  for (const projectId of projectRefCounts.keys()) {
    if (pendingJoins.has(projectId) || joinedProjects.has(projectId)) continue;
    void joinProject(projectId).catch((error) => notifyError(error));
  }
}

function handleDisconnect() {
  for (const projectId of pendingJoins) {
    nextJoinAttempt(projectId);
  }
  pendingJoins.clear();
  joinedProjects.clear();
}

function handleBackgroundSnapshot(raw: BackgroundSnapshot) {
  const projectId = typeof raw?.project_id === "string" ? raw.project_id : null;
  if (!projectId) return;
  projectSnapshotListeners.get(projectId)?.forEach((listener) => listener(raw));
}

function handleBackgroundEvent(raw: BackgroundEvent) {
  const projectId = typeof raw?.project_id === "string" ? raw.project_id : null;
  if (!projectId) return;
  projectEventListeners.get(projectId)?.forEach((listener) => listener(raw));
}

function handleBackgroundError(raw: { type?: string; reason?: string }) {
  if (raw?.type === "invalid_project") return;
  notifyError(new Error(raw?.reason || "后台事件订阅失败"));
}

function handleIndexStatus(raw: Record<string, unknown> | undefined) {
  const projectId = typeof raw?.project_id === "string" ? raw.project_id : null;
  if (!projectId) return;
  projectIndexStatusListeners.get(projectId)?.forEach((listener) => listener(raw));
}

function handleIndexConfig() {
  indexConfigListeners.forEach((listener) => listener());
}

function bindHandlers() {
  const socket = getSocket();
  if (handlersBound && boundSocket === socket) return;
  if (boundSocket && boundSocket !== socket) {
    boundSocket.off("connect", handleConnect);
    boundSocket.off("disconnect", handleDisconnect);
    boundSocket.off("background:snapshot", handleBackgroundSnapshot);
    boundSocket.off("background:event", handleBackgroundEvent);
    boundSocket.off("background:error", handleBackgroundError);
    boundSocket.off("index:status", handleIndexStatus);
    boundSocket.off("index:config", handleIndexConfig);
  }

  handlersBound = true;
  boundSocket = socket;

  socket.on("connect", handleConnect);
  socket.on("disconnect", handleDisconnect);
  socket.on("background:snapshot", handleBackgroundSnapshot);
  socket.on("background:event", handleBackgroundEvent);
  socket.on("background:error", handleBackgroundError);
  socket.on("index:status", handleIndexStatus);
  socket.on("index:config", handleIndexConfig);
}

function notifyError(error: Error) {
  errorListeners.forEach((listener) => listener(error));
}

async function joinProject(projectId: string): Promise<void> {
  if (pendingJoins.has(projectId) || joinedProjects.has(projectId)) return;

  const attemptId = nextJoinAttempt(projectId);
  pendingJoins.add(projectId);
  const socket = await connectSocket();

  if (currentJoinAttempt(projectId) !== attemptId) {
    pendingJoins.delete(projectId);
    return;
  }

  await new Promise<void>((resolve, reject) => {
    const cleanup = () => {
      window.clearTimeout(timeout);
      socket.off("background:joined", onJoined);
      socket.off("background:error", onError);
    };

    const onJoined = (data: { project_id?: string }) => {
      if (data?.project_id !== projectId) return;
      cleanup();
      pendingJoins.delete(projectId);

      if (currentJoinAttempt(projectId) !== attemptId) {
        if ((projectRefCounts.get(projectId) ?? 0) === 0) {
          leaveProject(projectId);
        }
        resolve();
        return;
      }

      joinedProjects.add(projectId);
      if ((projectRefCounts.get(projectId) ?? 0) === 0 || leaveAfterJoinProjects.has(projectId)) {
        leaveAfterJoinProjects.delete(projectId);
        joinedProjects.delete(projectId);
        leaveProject(projectId);
      }
      resolve();
    };

    const onError = (data: { type?: string; reason?: string }) => {
      if (data?.type !== "invalid_project") return;
      cleanup();
      pendingJoins.delete(projectId);

      if (currentJoinAttempt(projectId) !== attemptId) {
        resolve();
        return;
      }

      reject(new Error(data.reason || "后台事件订阅失败"));
    };

    socket.on("background:joined", onJoined);
    socket.on("background:error", onError);
    const timeout = window.setTimeout(() => {
      cleanup();
      pendingJoins.delete(projectId);

      if (currentJoinAttempt(projectId) !== attemptId) {
        resolve();
        return;
      }

      reject(new Error("加入后台项目房间超时"));
    }, 5000);
    socket.emit("background:join", { project_id: projectId });
  });
}

function leaveProject(projectId: string): void {
  const socket = getSocket();
  if (!socket.connected) return;
  socket.emit("background:leave", { project_id: projectId });
}

export async function requestBackgroundSnapshot(projectId: string): Promise<BackgroundSnapshot> {
  bindHandlers();
  const socket = await connectSocket();
  return await joinProjectAndWaitForSnapshot(socket, projectId);
}

export function subscribeBackgroundEvents(
  projectId: string,
  onEvent: (event: BackgroundEvent) => void,
  onError?: (error: Error) => void,
): BackgroundEventSubscription {
  return subscribeBackgroundProjection(projectId, undefined, onEvent, onError);
}

/**
 * 订阅项目的索引状态推送（index:status，按项目房间）与全局索引配置变更
 * （index:config，广播）。projectId 传 "__global__" 时仅订阅 index:config。
 */
export function subscribeIndexStatus(
  projectId: string,
  onStatus?: IndexStatusListener,
  onConfig?: IndexConfigListener,
): BackgroundEventSubscription {
  bindHandlers();

  let roomSub: BackgroundEventSubscription | null = null;
  if (projectId !== "__global__" && onStatus) {
    const listeners = projectIndexStatusListeners.get(projectId) ?? new Set<IndexStatusListener>();
    listeners.add(onStatus);
    projectIndexStatusListeners.set(projectId, listeners);
    // 加入项目房间（复用 background 房间引用计数管理）
    roomSub = subscribeBackgroundProjection(projectId, undefined, () => {}, undefined);
  }

  if (onConfig) {
    indexConfigListeners.add(onConfig);
  }

  return {
    close() {
      if (onStatus && projectId !== "__global__") {
        const listeners = projectIndexStatusListeners.get(projectId);
        if (listeners) {
          listeners.delete(onStatus);
          if (listeners.size === 0) {
            projectIndexStatusListeners.delete(projectId);
          }
        }
      }
      if (onConfig) {
        indexConfigListeners.delete(onConfig);
      }
      roomSub?.close();
    },
  };
}

export function subscribeBackgroundProjection(
  projectId: string,
  onSnapshot?: (snapshot: BackgroundSnapshot) => void,
  onEvent?: (event: BackgroundEvent) => void,
  onError?: (error: Error) => void,
): BackgroundProjectionSubscription {
  bindHandlers();

  if (onSnapshot) {
    const listeners =
      projectSnapshotListeners.get(projectId) ?? new Set<BackgroundSnapshotListener>();
    listeners.add(onSnapshot);
    projectSnapshotListeners.set(projectId, listeners);
  }

  if (onEvent) {
    const listeners = projectEventListeners.get(projectId) ?? new Set<BackgroundListener>();
    listeners.add(onEvent);
    projectEventListeners.set(projectId, listeners);
  }

  if (onError) {
    errorListeners.add(onError);
  }

  const nextCount = (projectRefCounts.get(projectId) ?? 0) + 1;
  projectRefCounts.set(projectId, nextCount);
  if (nextCount === 1) {
    leaveAfterJoinProjects.delete(projectId);
    const socket = getSocket();
    if (socket.connected) {
      void joinProject(projectId).catch((error) => notifyError(error));
    } else {
      void connectSocket().catch((error) => notifyError(error));
    }
  }

  return {
    close() {
      if (onSnapshot) {
        const listeners = projectSnapshotListeners.get(projectId);
        if (listeners) {
          listeners.delete(onSnapshot);
          if (listeners.size === 0) {
            projectSnapshotListeners.delete(projectId);
          }
        }
      }

      if (onEvent) {
        const listeners = projectEventListeners.get(projectId);
        if (listeners) {
          listeners.delete(onEvent);
          if (listeners.size === 0) {
            projectEventListeners.delete(projectId);
          }
        }
      }
      if (onError) {
        errorListeners.delete(onError);
      }

      const currentCount = projectRefCounts.get(projectId) ?? 0;
      if (currentCount <= 1) {
        projectRefCounts.delete(projectId);
        leaveAfterJoinProjects.add(projectId);
        if (pendingJoins.has(projectId)) {
          return;
        }

        leaveAfterJoinProjects.delete(projectId);
        joinedProjects.delete(projectId);
        leaveProject(projectId);
        return;
      }

      projectRefCounts.set(projectId, currentCount - 1);
    },
  };
}
