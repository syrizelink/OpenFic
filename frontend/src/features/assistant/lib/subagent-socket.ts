import type { ActiveSubagentState, AgentEvent } from "@/lib/agent.types";
import { connectSocket, getSocket } from "../../../lib/socket-client";
import i18n from "@/i18n";
import { AGENT_SOCKET_EVENTS, toAgentEvent } from "./agent-socket-events";
import { getString, isRecord } from "./tool-result-normalization";

export const SUBAGENT_SOCKET_EVENTS = {
  status: "agent:subagent_status",
  joinSubagents: "agent:join_subagents",
  joinedSubagents: "agent:joined_subagents",
  leaveSubagents: "agent:leave_subagents",
  joinSubagent: "agent:join_subagent",
  joinedSubagent: "agent:joined_subagent",
  leaveSubagent: "agent:leave_subagent",
  connect: "connect",
  error: "agent:error",
  connectError: "connect_error",
} as const;

type SocketHandler = (data: unknown) => void;

export interface SubagentSocketLike {
  on(event: string, handler: SocketHandler): void;
  off(event: string, handler: SocketHandler): void;
  emit(event: string, payload: Record<string, unknown>): void;
}

interface SubagentSocketConnector {
  connect(): Promise<SubagentSocketLike>;
  get(): SubagentSocketLike;
}

const SOCKET_JOIN_TIMEOUT_MS = 5000;

function matchesParentSession(sessionId: string, data: Record<string, unknown>): boolean {
  const eventSessionId = getString(data.parent_session_id) || getString(data.session_id);
  return !eventSessionId || eventSessionId === sessionId;
}

export function toSubagentStatusEvent(
  sessionId: string,
  rawData: unknown
): ActiveSubagentState | null {
  const data = isRecord(rawData) ? rawData : {};
  if (!matchesParentSession(sessionId, data)) return null;
  const metadata = isRecord(data.metadata) ? data.metadata : null;
  const pendingApproval = isRecord(data.pending_approval) ? data.pending_approval : null;

  return {
    childRunId: getString(data.child_run_id) || "",
    childThreadId: getString(data.child_thread_id) || "",
    agentKey: (getString(data.agent_key) || "") as ActiveSubagentState["agentKey"],
    agentNumber: getString(data.agent_number) || getString(metadata?.agent_number),
    status: (getString(data.status) || "") as ActiveSubagentState["status"],
    queuedMessages: Number(data.queued_messages ?? 0),
    isActive: data.is_active === true,
    pendingApproval,
  };
}

function waitForJoinAck(
  socket: SubagentSocketLike,
  {
    joinEvent,
    joinedEvent,
    payload,
    matchesJoined,
    invalidType,
    timeoutMessage,
    invalidMessage,
  }: {
    joinEvent: string;
    joinedEvent: string;
    payload: Record<string, unknown>;
    matchesJoined: (data: Record<string, unknown>) => boolean;
    invalidType: string;
    timeoutMessage: string;
    invalidMessage: string;
  }
): Promise<void> {
  return new Promise((resolve, reject) => {
    let timeout: ReturnType<typeof globalThis.setTimeout> | null = null;

    const cleanup = () => {
      if (timeout !== null) {
        globalThis.clearTimeout(timeout);
      }
      socket.off(joinedEvent, onJoined);
      socket.off(SUBAGENT_SOCKET_EVENTS.error, onError);
    };

    const onJoined = (data: unknown) => {
      if (!isRecord(data) || !matchesJoined(data)) return;
      cleanup();
      resolve();
    };

    const onError = (data: unknown) => {
      if (!isRecord(data) || getString(data.type) !== invalidType) return;
      cleanup();
      reject(new Error(getString(data.reason) || invalidMessage));
    };

    socket.on(joinedEvent, onJoined);
    socket.on(SUBAGENT_SOCKET_EVENTS.error, onError);
    timeout = globalThis.setTimeout(() => {
      cleanup();
      reject(new Error(timeoutMessage));
    }, SOCKET_JOIN_TIMEOUT_MS);
    socket.emit(joinEvent, payload);
  });
}

export function createSubagentSocketTransport(
  connector: SubagentSocketConnector = {
    connect: connectSocket,
    get: getSocket,
  }
) {
  async function joinSubagentStatusStream(sessionId: string): Promise<void> {
    const socket = await connector.connect();
    await waitForJoinAck(socket, {
      joinEvent: SUBAGENT_SOCKET_EVENTS.joinSubagents,
      joinedEvent: SUBAGENT_SOCKET_EVENTS.joinedSubagents,
      payload: { session_id: sessionId },
      matchesJoined: (data) => getString(data.session_id) === sessionId,
      invalidType: "invalid_session",
      timeoutMessage: i18n.t("assistant.joinSubagentStatusTimeout"),
      invalidMessage: i18n.t("assistant.joinSubagentStatusFailed"),
    });
  }

  function leaveSubagentStatusStream(sessionId: string): void {
    connector.get().emit(SUBAGENT_SOCKET_EVENTS.leaveSubagents, {
      session_id: sessionId,
    });
  }

  function subscribeSubagentStatusEvents(
    sessionId: string,
    onEvent: (event: ActiveSubagentState) => void,
    onError?: (error: Error) => void
  ): () => void {
    const socket = connector.get();
    let hasJoinedRoom = false;
    const statusHandler = (data: unknown) => {
      const event = toSubagentStatusEvent(sessionId, data);
      if (event) onEvent(event);
    };
    const joinedHandler = (data: unknown) => {
      if (!isRecord(data) || getString(data.session_id) !== sessionId) return;
      hasJoinedRoom = true;
    };
    const connectHandler = () => {
      if (!hasJoinedRoom) return;
      void joinSubagentStatusStream(sessionId).catch((error) => {
        onError?.(error instanceof Error ? error : new Error(i18n.t("assistant.subagentStatusReconnectFailed")));
      });
    };
    const connectError = (error: unknown) => {
      onError?.(error instanceof Error ? error : new Error(i18n.t("assistant.subagentStatusSubscribeFailed")));
    };

    socket.on(SUBAGENT_SOCKET_EVENTS.status, statusHandler);
    socket.on(SUBAGENT_SOCKET_EVENTS.joinedSubagents, joinedHandler);
    socket.on(SUBAGENT_SOCKET_EVENTS.connect, connectHandler);
    socket.on(SUBAGENT_SOCKET_EVENTS.connectError, connectError);

    return () => {
      socket.off(SUBAGENT_SOCKET_EVENTS.joinedSubagents, joinedHandler);
      socket.off(SUBAGENT_SOCKET_EVENTS.connect, connectHandler);
      socket.off(SUBAGENT_SOCKET_EVENTS.connectError, connectError);
      socket.off(SUBAGENT_SOCKET_EVENTS.status, statusHandler);
      leaveSubagentStatusStream(sessionId);
    };
  }

  async function joinSubagentSession(childThreadId: string): Promise<void> {
    const socket = await connector.connect();
    await waitForJoinAck(socket, {
      joinEvent: SUBAGENT_SOCKET_EVENTS.joinSubagent,
      joinedEvent: SUBAGENT_SOCKET_EVENTS.joinedSubagent,
      payload: { child_thread_id: childThreadId },
      matchesJoined: (data) => getString(data.child_thread_id) === childThreadId,
      invalidType: "invalid_child_thread",
      timeoutMessage: i18n.t("assistant.joinSubagentSessionTimeout"),
      invalidMessage: i18n.t("assistant.joinSubagentSessionFailed"),
    });
  }

  function leaveSubagentSession(childThreadId: string): void {
    connector.get().emit(SUBAGENT_SOCKET_EVENTS.leaveSubagent, {
      child_thread_id: childThreadId,
    });
  }

  function subscribeSubagentSessionEvents(
    childThreadId: string,
    onEvent: (event: AgentEvent) => void,
    onError?: (error: Error) => void
  ): () => void {
    const socket = connector.get();
    let hasJoinedRoom = false;
    const joinedHandler = (data: unknown) => {
      if (!isRecord(data) || getString(data.child_thread_id) !== childThreadId) return;
      hasJoinedRoom = true;
    };
    const connectHandler = () => {
      if (!hasJoinedRoom) return;
      void joinSubagentSession(childThreadId).catch((error) => {
        onError?.(error instanceof Error ? error : new Error(i18n.t("assistant.subagentSessionReconnectFailed")));
      });
    };
    const connectError = (error: unknown) => {
      onError?.(error instanceof Error ? error : new Error(i18n.t("assistant.subagentSessionSubscribeFailed")));
    };
    const handlers = AGENT_SOCKET_EVENTS.map((eventName) => {
      const handler = (data: unknown) => {
        const event = toAgentEvent(eventName, childThreadId, data);
        if (event) onEvent(event);
      };
      socket.on(eventName, handler);
      return { eventName, handler };
    });

    socket.on(SUBAGENT_SOCKET_EVENTS.joinedSubagent, joinedHandler);
    socket.on(SUBAGENT_SOCKET_EVENTS.connect, connectHandler);
    socket.on(SUBAGENT_SOCKET_EVENTS.connectError, connectError);

    return () => {
      socket.off(SUBAGENT_SOCKET_EVENTS.joinedSubagent, joinedHandler);
      socket.off(SUBAGENT_SOCKET_EVENTS.connect, connectHandler);
      socket.off(SUBAGENT_SOCKET_EVENTS.connectError, connectError);
      handlers.forEach(({ eventName, handler }) => socket.off(eventName, handler));
      leaveSubagentSession(childThreadId);
    };
  }

  return {
    joinSubagentStatusStream,
    leaveSubagentStatusStream,
    subscribeSubagentStatusEvents,
    joinSubagentSession,
    leaveSubagentSession,
    subscribeSubagentSessionEvents,
  };
}

const subagentSocketTransport = createSubagentSocketTransport();

export const {
  joinSubagentStatusStream,
  leaveSubagentStatusStream,
  subscribeSubagentStatusEvents,
  joinSubagentSession,
  leaveSubagentSession,
  subscribeSubagentSessionEvents,
} = subagentSocketTransport;
