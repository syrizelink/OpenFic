import type { AgentEvent } from "@/lib/agent.types";
import { connectSocket, getSocket } from "@/lib/socket-client";
import { AGENT_SOCKET_EVENTS, toAgentEvent } from "./agent-socket-events";
import { getString, isRecord } from "./tool-result-normalization";

export function subscribeAgentSessionEvents(
  sessionId: string,
  onEvent: (event: AgentEvent) => void,
  onError?: (error: Error) => void
): () => void {
  const activeSocket = getSocket();
  const connectError = (error: Error) => onError?.(error);
  const handlers = AGENT_SOCKET_EVENTS.map((eventName) => {
    const handler = (data: unknown) => {
      const event = toAgentEvent(eventName, sessionId, data);
      if (event) onEvent(event);
    };
    activeSocket.on(eventName, handler);
    return { eventName, handler };
  });

  activeSocket.on("connect_error", connectError);

  return () => {
    activeSocket.off("connect_error", connectError);
    handlers.forEach(({ eventName, handler }) => activeSocket.off(eventName, handler));
    activeSocket.emit("agent:leave", { session_id: sessionId });
  };
}

export async function joinAgentSession(sessionId: string): Promise<void> {
  const activeSocket = getSocket();
  await connectSocket();

  return new Promise((resolve, reject) => {
    const cleanup = () => {
      window.clearTimeout(timeout);
      activeSocket.off("agent:joined", onJoined);
      activeSocket.off("agent:error", onError);
    };
    const onJoined = (data: unknown) => {
      if (!isRecord(data) || getString(data.session_id) !== sessionId) return;
      cleanup();
      resolve();
    };
    const onError = (data: unknown) => {
      if (isRecord(data) && data.type === "invalid_session") {
        cleanup();
        reject(new Error(getString(data.reason) || "加入 Agent 会话失败"));
      }
    };

    activeSocket.on("agent:joined", onJoined);
    activeSocket.on("agent:error", onError);
    const timeout = window.setTimeout(() => {
      cleanup();
      reject(new Error("加入 Agent 会话超时"));
    }, 5000);
    activeSocket.emit("agent:join", { session_id: sessionId });
  });
}
