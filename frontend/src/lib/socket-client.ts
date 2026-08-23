import { io, type Socket } from "socket.io-client";

import i18n from "../i18n";
import { handleAuthenticationFailure } from "./api-client";
import { publishSocketDiagnostic, type SocketDiagnosticPayload } from "./desktop-appearance-bridge";
import { getConfiguredBackendBaseUrl, getRuntimeConfig } from "./runtime-config";

export type SocketConnectionStatus = "connected" | "disconnected";

const DEFAULT_CONNECTION_TIMEOUT_MS = 30_000;

interface SocketClientState {
  socket: Socket | null;
  socketUrl: string | undefined;
  connectPromise: Promise<Socket> | null;
  connectionStartedAt: number | null;
  lastConnectionError: string | null;
  lastConnectionHttpStatus: number | undefined;
  lastConnectionTransport: string | undefined;
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
    lastConnectionError: null,
    lastConnectionHttpStatus: undefined,
    lastConnectionTransport: undefined,
    connectionStatus: "disconnected",
    statusListeners: new Set<() => void>(),
    statusBoundSocket: null,
  };
  window.__openficSocketClientState.lastConnectionError ??= null;
  window.__openficSocketClientState.lastConnectionHttpStatus ??= undefined;
  window.__openficSocketClientState.lastConnectionTransport ??= undefined;
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

function getXhrHttpStatus(error: unknown): number | undefined {
  const candidate = error as { description?: unknown };
  return typeof candidate.description === "number" &&
    Number.isFinite(candidate.description) &&
    candidate.description > 0
    ? candidate.description
    : undefined;
}

function describeSocketHttpStatus(status: number): string {
  if (status === 404) return i18n.t("common.socketProbeNotFound");
  if (status === 403) return i18n.t("common.socketProbeForbidden");
  return i18n.t("common.socketHttpStatus", { status });
}

async function probeSocketIoEndpoint(baseUrl: string): Promise<string | null> {
  const url = `${baseUrl.replace(/\/+$/, "")}/socket.io/?EIO=4&transport=polling`;
  try {
    const response = await fetch(url, {
      method: "GET",
      cache: "no-store",
      credentials: "include",
    });
    if (response.status === 401) handleAuthenticationFailure();
    if (response.ok) return i18n.t("common.socketProbeOk");
    return describeSocketHttpStatus(response.status);
  } catch {
    return i18n.t("common.socketProbeFailed");
  }
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
    state.lastConnectionError = null;
    state.lastConnectionHttpStatus = undefined;
    state.lastConnectionTransport = undefined;
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
    state.lastConnectionError = getErrorMessage(error);
    state.lastConnectionHttpStatus = getXhrHttpStatus(error);
    if (state.lastConnectionHttpStatus === 401) handleAuthenticationFailure();
    state.lastConnectionTransport = getSocketTransport(socket);
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

  return getConfiguredBackendBaseUrl() ?? undefined;
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
    state.lastConnectionHttpStatus = undefined;
    state.statusBoundSocket = null;
    setConnectionStatus("disconnected");
  }

  if (!state.socket) {
    state.socket = nextSocketUrl
      ? io(nextSocketUrl, {
          path: "/socket.io",
          autoConnect: false,
          withCredentials: true,
          transports: ["websocket", "polling"],
          tryAllTransports: true,
        })
      : io({
          path: "/socket.io",
          autoConnect: false,
          withCredentials: true,
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

  state.lastConnectionError = null;
  state.lastConnectionHttpStatus = undefined;
  state.lastConnectionTransport = undefined;
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

    const rejectWithDiagnosis = async () => {
      const details: string[] = [];
      if (state.lastConnectionHttpStatus) {
        details.push(describeSocketHttpStatus(state.lastConnectionHttpStatus));
      } else if (state.lastConnectionError) {
        details.push(state.lastConnectionError);
      } else {
        details.push(
          i18n.t("common.socketConnectionTimeout", {
            seconds: Math.ceil(timeoutMs / 1000),
          }),
        );
      }

      if (!state.lastConnectionHttpStatus && state.socketUrl) {
        const probe = await probeSocketIoEndpoint(state.socketUrl);
        if (probe) details.push(probe);
      }

      if (state.lastConnectionTransport) {
        details.push(
          i18n.t("common.socketTransport", { transport: state.lastConnectionTransport }),
        );
      }
      if (state.socketUrl) {
        details.push(i18n.t("common.socketAddress", { address: state.socketUrl }));
      }

      const error = new Error(
        i18n.t("common.socketConnectionFailed", {
          details: details.join(i18n.t("common.errorDetailSeparator")),
        }),
      );
      reportSocketDiagnostic("connection-timeout", activeSocket, {
        active: activeSocket.active,
        durationMs: getConnectionDuration(),
        message: error.message,
      });
      activeSocket.disconnect();
      reject(error);
    };

    const timeout = window.setTimeout(() => {
      cleanup();
      void rejectWithDiagnosis();
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
