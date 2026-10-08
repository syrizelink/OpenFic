import { useCallback, useEffect, useRef, useState } from "react";

import type { AgentMessage } from "@/lib/agent.types";

export interface AgentMessagePage {
  messages: AgentMessage[];
  messagesCursor: number | null;
  messagesHasMore: boolean;
}

interface AgentMessagePaginationState {
  messagesCursor: number | null;
  messagesHasMore: boolean;
  isLoadingEarlier: boolean;
  hasEarlierError: boolean;
  generation: number;
}

export function prependAgentMessages(
  current: AgentMessage[],
  older: AgentMessage[],
): AgentMessage[] {
  const ids = new Set(current.map((message) => message.id));
  const unique = older.filter((message) => {
    if (ids.has(message.id)) return false;
    ids.add(message.id);
    return true;
  });
  return unique.length ? [...unique, ...current] : current;
}

export function createAgentMessagePagination(
  onChange: (state: AgentMessagePaginationState) => void,
) {
  let key: string | null = null;
  let current: AgentMessagePaginationState = {
    messagesCursor: null,
    messagesHasMore: false,
    isLoadingEarlier: false,
    hasEarlierError: false,
    generation: 0,
  };
  const update = (next: AgentMessagePaginationState) => {
    current = next;
    onChange(next);
  };
  return {
    get current() {
      return current;
    },
    reset(
      this: void,
      nextKey: string | null,
      page?: Pick<AgentMessagePage, "messagesCursor" | "messagesHasMore">,
    ) {
      key = nextKey;
      update({
        messagesCursor: page?.messagesCursor ?? null,
        messagesHasMore: page?.messagesHasMore ?? false,
        isLoadingEarlier: false,
        hasEarlierError: false,
        generation: current.generation + 1,
      });
    },
    invalidate(this: void) {
      update({
        ...current,
        generation: current.generation + 1,
        isLoadingEarlier: false,
        hasEarlierError: false,
      });
    },
    async load(
      fetchPage: (key: string, cursor: number) => Promise<AgentMessagePage>,
      applyPage: (messages: AgentMessage[]) => void,
      retry = false,
    ): Promise<void> {
      if (
        !key ||
        current.isLoadingEarlier ||
        !current.messagesHasMore ||
        current.messagesCursor === null ||
        (current.hasEarlierError && !retry)
      )
        return;
      const { generation, messagesCursor: cursor } = current;
      update({ ...current, isLoadingEarlier: true, hasEarlierError: false });
      try {
        const page = await fetchPage(key, cursor);
        if (generation !== current.generation) return;
        applyPage(page.messages);
        update({
          ...current,
          messagesCursor: page.messagesCursor,
          messagesHasMore:
            page.messagesHasMore && page.messagesCursor !== null && page.messagesCursor < cursor,
          isLoadingEarlier: false,
        });
      } catch {
        if (generation !== current.generation) return;
        update({ ...current, isLoadingEarlier: false, hasEarlierError: true });
      }
    },
  };
}

export function useAgentMessagePagination(
  fetchPage: (key: string, cursor: number) => Promise<AgentMessagePage>,
  applyPage: (messages: AgentMessage[]) => void,
) {
  const [state, setState] = useState<AgentMessagePaginationState>({
    messagesCursor: null,
    messagesHasMore: false,
    isLoadingEarlier: false,
    hasEarlierError: false,
    generation: 0,
  });
  const controllerRef = useRef<ReturnType<typeof createAgentMessagePagination> | null>(null);
  if (!controllerRef.current) controllerRef.current = createAgentMessagePagination(setState);
  const controller = controllerRef.current;
  const loadEarlier = useCallback(
    (retry = false) => controller.load(fetchPage, applyPage, retry),
    [controller, fetchPage, applyPage],
  );
  const getPaginationGeneration = useCallback(() => controller.current.generation, [controller]);
  useEffect(() => () => controller.invalidate(), [controller]);
  return {
    ...state,
    loadEarlier,
    resetPagination: controller.reset,
    invalidatePagination: controller.invalidate,
    getPaginationGeneration,
  };
}
