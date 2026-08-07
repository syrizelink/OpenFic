import type { AgentEvent } from "@/lib/agent.types";

const DEFAULT_MAX_DELAY_MS = 50;

export function isStreamingDeltaEvent(event: AgentEvent): boolean {
  return Boolean(event.payload?.is_delta && ["text", "reasoning", "tool"].includes(event.type));
}

export interface StreamingDeltaCoalescer {
  push(event: AgentEvent): void;
  flush(): void;
  readonly pendingCount: number;
  dispose(): void;
}

export function createStreamingDeltaCoalescer(
  applyEvents: (events: AgentEvent[]) => void,
  maxDelayMs: number = DEFAULT_MAX_DELAY_MS,
): StreamingDeltaCoalescer {
  let queue: AgentEvent[] = [];
  let rafId: number | null = null;
  let timerId: number | null = null;

  const flush = () => {
    if (rafId !== null) {
      window.cancelAnimationFrame(rafId);
      rafId = null;
    }
    if (timerId !== null) {
      window.clearTimeout(timerId);
      timerId = null;
    }
    const events = queue;
    queue = [];
    if (events.length > 0) {
      applyEvents(events);
    }
  };

  const schedule = () => {
    if (rafId === null) {
      rafId = window.requestAnimationFrame(() => {
        rafId = null;
        flush();
      });
    }
    if (timerId === null) {
      timerId = window.setTimeout(() => {
        timerId = null;
        flush();
      }, maxDelayMs);
    }
  };

  return {
    push(event) {
      queue.push(event);
      schedule();
    },
    flush,
    get pendingCount() {
      return queue.length;
    },
    dispose() {
      flush();
    },
  };
}
