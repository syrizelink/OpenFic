import { io, type Socket } from "socket.io-client";

import { getRuntimeConfig } from "./runtime-config";

export type SocketConnectionStatus = "connected" | "disconnected";

interface SocketClientState {
  socket: Socket | null;
  socketUrl: string | undefined;
  connectPromise: Promise<Socket> | null;
  connectionStatus: SocketConnectionStatus;
  statusListeners: Set<() => void>;
  statusBoundSocket: Socket | null;
}

declare global {
  interface Window {
    __openficSocketClientState?: SocketClientState;
  }
}

function getSocketState(): SocketClientState {
  window.__openficSocketClientState ??= {
    socket: null,
    socketUrl: undefined,
    connectPromise: null,
    connectionStatus: "disconnected",
    statusListeners: new Set<() => void>(),
    statusBoundSocket: null,
  };
  return window.__openficSocketClientState;
}

function setConnectionStatus(nextStatus: SocketConnectionStatus): void {
  const state = getSocketState();
  if (state.connectionStatus === nextStatus) return;
  state.connectionStatus = nextStatus;
  state.statusListeners.forEach((listener) => listener());
}

export function getSocketConnectionStatus(): SocketConnectionStatus {
  return getSocketState().connectionStatus;
}

export function subscribeSocketConnectionStatus(listener: () => void): () => void {
  const state = getSocketState();
  state.statusListeners.add(listener);
  return () => state.statusListeners.delete(listener);
}

function bindConnectionStatus(socket: Socket): void {
  const state = getSocketState();
  if (state.statusBoundSocket === socket) return;
  state.statusBoundSocket = socket;
  socket.on("connect", () => setConnectionStatus("connected"));
  socket.on("disconnect", () => setConnectionStatus("disconnected"));
  socket.on("connect_error", () => setConnectionStatus("disconnected"));
}

function getSocketUrl(): string | undefined {
  const runtimeBackendUrl = getRuntimeConfig()?.backendBaseUrl;
  if (runtimeBackendUrl) return runtimeBackendUrl;

  const explicitBackendUrl = import.meta.env.VITE_BACKEND_URL as string | undefined;
  if (explicitBackendUrl) return explicitBackendUrl.replace(/\/$/, "");

  const { protocol, hostname, port } = window.location;
  const isLocalHost = hostname === "localhost" || hostname === "127.0.0.1";
  if (isLocalHost && port !== "8000") {
    return `${protocol}//${hostname}:8000`;
  }

  return undefined;
}

export function getSocket(): Socket {
  const state = getSocketState();
  const nextSocketUrl = getSocketUrl();
  if (state.socket && state.socketUrl !== nextSocketUrl) {
    state.socket.disconnect();
    state.socket = null;
    state.socketUrl = undefined;
    state.connectPromise = null;
    state.statusBoundSocket = null;
    setConnectionStatus("disconnected");
  }

  if (!state.socket) {
    state.socket = nextSocketUrl
      ? io(nextSocketUrl, {
          path: "/socket.io",
          autoConnect: false,
          transports: ["websocket", "polling"],
        })
      : io({
          path: "/socket.io",
          autoConnect: false,
          transports: ["websocket", "polling"],
        });
    state.socketUrl = nextSocketUrl;
    bindConnectionStatus(state.socket);
    setConnectionStatus(state.socket.connected ? "connected" : "disconnected");
  }

  return state.socket;
}

export function connectSocket(): Promise<Socket> {
  const state = getSocketState();
  const activeSocket = getSocket();
  if (activeSocket.connected) return Promise.resolve(activeSocket);
  if (state.connectPromise) return state.connectPromise;

  state.connectPromise = new Promise<Socket>((resolve, reject) => {
    const cleanup = () => {
      window.clearTimeout(timeout);
      activeSocket.off("connect", onConnect);
      activeSocket.off("connect_error", onError);
    };

    const onConnect = () => {
      cleanup();
      resolve(activeSocket);
    };

    const onError = (error: Error) => {
      cleanup();
      reject(error);
    };

    activeSocket.once("connect", onConnect);
    activeSocket.once("connect_error", onError);
    const timeout = window.setTimeout(() => {
      cleanup();
      reject(new Error("WebSocket 连接超时"));
    }, 5000);
    activeSocket.connect();
  }).finally(() => {
    state.connectPromise = null;
  });

  return state.connectPromise;
}
