import { io, type Socket } from "socket.io-client";
import { getRuntimeConfig } from "./runtime-config";

let socket: Socket | null = null;
let socketUrl: string | undefined;
let connectPromise: Promise<Socket> | null = null;

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
  const nextSocketUrl = getSocketUrl();
  if (socket && socketUrl !== nextSocketUrl) {
    socket.disconnect();
    socket = null;
    connectPromise = null;
  }

  if (!socket) {
    socket = nextSocketUrl
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
    socketUrl = nextSocketUrl;
  }

  return socket;
}

export function connectSocket(): Promise<Socket> {
  const activeSocket = getSocket();
  if (activeSocket.connected) return Promise.resolve(activeSocket);
  if (connectPromise) return connectPromise;

  connectPromise = new Promise<Socket>((resolve, reject) => {
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
    connectPromise = null;
  });

  return connectPromise;
}

export function disposeSocketForHmr(): void {
  socket?.disconnect();
  socket = null;
  socketUrl = undefined;
  connectPromise = null;
}
