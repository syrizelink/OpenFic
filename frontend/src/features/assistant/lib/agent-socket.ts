import i18n from "@/i18n";
import type { AgentEvent } from "@/lib/agent.types";
import { connectSocket, getSocket } from "@/lib/socket-client";

import { AGENT_SOCKET_EVENTS, toAgentEvent } from "./agent-socket-events";
import { getString, isRecord } from "./tool-result-normalization";

const pendingAgentSessionJoins = new Map<string, Promise<void>>();

export function subscribeAgentSessionEvents(
  sessionId: string,
  onEvent: (event: AgentEvent) => void,
  onError?: (error: Error) => void,
): () => void {
  const activeSocket = getSocket();
  const connectError = (error: Error) => onError?.(error);
  let hasJoinedRoom = false;
  const joinedHandler = (data: unknown) => {
    if (!isRecord(data) || getString(data.session_id) !== sessionId) return;
    hasJoinedRoom = true;
  };
  const connectHandler = () => {
    if (!hasJoinedRoom) return;
    void joinAgentSession(sessionId).catch((error) => {
      onError?.(
        error instanceof Error ? error : new Error(i18n.t("assistant.joinAgentSessionFailed")),
      );
    });
  };
  const handlers = AGENT_SOCKET_EVENTS.map((eventName) => {
    const handler = (data: unknown) => {
      const event = toAgentEvent(eventName, sessionId, data);
      if (event) onEvent(event);
    };
    activeSocket.on(eventName, handler);
    return { eventName, handler };
  });

  activeSocket.on("agent:joined", joinedHandler);
  activeSocket.on("connect", connectHandler);
  activeSocket.on("connect_error", connectError);

  return () => {
    activeSocket.off("agent:joined", joinedHandler);
    activeSocket.off("connect", connectHandler);
    activeSocket.off("connect_error", connectError);
    handlers.forEach(({ eventName, handler }) => activeSocket.off(eventName, handler));
    activeSocket.emit("agent:leave", { session_id: sessionId });
  };
}

export async function joinAgentSession(sessionId: string): Promise<void> {
  const pendingJoin = pendingAgentSessionJoins.get(sessionId);
  if (pendingJoin) return pendingJoin;

  const joinPromise = (async () => {
    const activeSocket = getSocket();
    await connectSocket({ force: true });

    await new Promise<void>((resolve, reject) => {
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
          reject(new Error(getString(data.reason) || i18n.t("assistant.joinAgentSessionFailed")));
        }
      };

      activeSocket.on("agent:joined", onJoined);
      activeSocket.on("agent:error", onError);
      const timeout = window.setTimeout(() => {
        cleanup();
        reject(new Error(i18n.t("assistant.joinAgentSessionTimeout")));
      }, 5000);
      activeSocket.emit("agent:join", { session_id: sessionId });
    });
  })();
  pendingAgentSessionJoins.set(sessionId, joinPromise);
  void joinPromise.then(
    () => pendingAgentSessionJoins.delete(sessionId),
    () => pendingAgentSessionJoins.delete(sessionId),
  );
  return joinPromise;
}
