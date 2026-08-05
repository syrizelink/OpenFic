import { io, type Socket } from "socket.io-client";

import { publishSocketDiagnostic, type SocketDiagnosticPayload } from "./desktop-appearance-bridge";
import { getRuntimeConfig } from "./runtime-config";

export type SocketConnectionStatus = "connected" | "disconnected";

const DEFAULT_CONNECTION_TIMEOUT_MS = 30_000;

interface SocketClientState {
  socket: Socket | null;
  socketUrl: string | undefined;
  connectPromise: Promise<Socket> | null;
  connectionStartedAt: number | null;
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
    connectionStartedAt: null,
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

function getSocketTransport(socket: Socket): string | undefined {
  return socket.io.engine?.transport.name;
}

function getConnectionDuration(): number | undefined {
  const startedAt = getSocketState().connectionStartedAt;
  return startedAt === null ? undefined : Date.now() - startedAt;
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function reportSocketDiagnostic(
  event: SocketDiagnosticPayload["event"],
  socket: Socket,
  details: Omit<SocketDiagnosticPayload, "event" | "transport" | "url"> = {},
): void {
  publishSocketDiagnostic({
    event,
    url: getSocketState().socketUrl ?? window.location.origin,
    transport: getSocketTransport(socket),
    ...details,
  });
}

function bindConnectionStatus(socket: Socket): void {
  const state = getSocketState();
  if (state.statusBoundSocket === socket) return;
  state.statusBoundSocket = socket;
  socket.on("connect", () => {
    setConnectionStatus("connected");
    reportSocketDiagnostic("connected", socket, { durationMs: getConnectionDuration() });
    state.connectionStartedAt = null;
  });
  socket.on("disconnect", (reason) => {
    setConnectionStatus("disconnected");
    reportSocketDiagnostic("disconnected", socket, { active: socket.active, message: reason });
  });
  socket.on("connect_error", (error) => {
    setConnectionStatus("disconnected");
    reportSocketDiagnostic("connect-error", socket, {
      active: socket.active,
      message: getErrorMessage(error),
    });
  });
  socket.io.on("reconnect_attempt", (attempt) => {
    reportSocketDiagnostic("reconnect-attempt", socket, { attempt });
  });
  socket.io.on("reconnect_failed", () => {
    reportSocketDiagnostic("reconnect-failed", socket, { active: socket.active });
  });
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
    state.connectionStartedAt = null;
    state.statusBoundSocket = null;
    setConnectionStatus("disconnected");
  }

  if (!state.socket) {
    state.socket = nextSocketUrl
      ? io(nextSocketUrl, {
          path: "/socket.io",
          autoConnect: false,
          transports: ["websocket", "polling"],
          tryAllTransports: true,
        })
      : io({
          path: "/socket.io",
          autoConnect: false,
          transports: ["websocket", "polling"],
          tryAllTransports: true,
        });
    state.socketUrl = nextSocketUrl;
    bindConnectionStatus(state.socket);
    setConnectionStatus(state.socket.connected ? "connected" : "disconnected");
  }

  return state.socket;
}

export function connectSocket({
  force = false,
  timeoutMs = DEFAULT_CONNECTION_TIMEOUT_MS,
}: {
  force?: boolean;
  timeoutMs?: number;
} = {}): Promise<Socket> {
  const state = getSocketState();
  const activeSocket = getSocket();
  if (activeSocket.connected) return Promise.resolve(activeSocket);
  if (state.connectPromise) {
    if (force && activeSocket.active) {
      // Cancel a pending automatic backoff before an explicit user action.
      activeSocket.disconnect();
      state.connectionStartedAt = Date.now();
      reportSocketDiagnostic("connect-start", activeSocket, { active: activeSocket.active });
      activeSocket.connect();
    }
    return state.connectPromise;
  }

  state.connectionStartedAt = Date.now();
  reportSocketDiagnostic("connect-start", activeSocket, { active: activeSocket.active });
  const connectPromise = new Promise<Socket>((resolve, reject) => {
    const cleanup = () => {
      window.clearTimeout(timeout);
      activeSocket.off("connect", onConnect);
    };

    const onConnect = () => {
      cleanup();
      resolve(activeSocket);
    };

    const timeout = window.setTimeout(() => {
      cleanup();
      const error = new Error(`Socket 连接超时（${Math.ceil(timeoutMs / 1000)} 秒）`);
      reportSocketDiagnostic("connection-timeout", activeSocket, {
        active: activeSocket.active,
        durationMs: getConnectionDuration(),
        message: error.message,
      });
      activeSocket.disconnect();
      reject(error);
    }, timeoutMs);

    activeSocket.once("connect", onConnect);
    if (force && activeSocket.active) activeSocket.disconnect();
    activeSocket.connect();
  });
  state.connectPromise = connectPromise;
  void connectPromise.then(
    () => {
      if (state.connectPromise === connectPromise) state.connectPromise = null;
    },
    () => {
      if (state.connectPromise === connectPromise) state.connectPromise = null;
    },
  );

  return connectPromise;
}
