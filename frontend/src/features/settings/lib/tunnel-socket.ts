import { connectSocket, getSocket } from "@/lib/socket-client";

import type { TunnelStatusEvent } from "./tunnels-api";

export function subscribeTunnelStatus(
  onStatus: (status: TunnelStatusEvent) => void,
  onReconnect: () => void,
): () => void {
  const socket = getSocket();
  const handleStatus = (status: TunnelStatusEvent) => onStatus(status);
  const handleConnect = () => onReconnect();

  socket.on("tunnel:status", handleStatus);
  socket.on("connect", handleConnect);

  if (!socket.connected) void connectSocket().catch(() => undefined);

  return () => {
    socket.off("tunnel:status", handleStatus);
    socket.off("connect", handleConnect);
  };
}
