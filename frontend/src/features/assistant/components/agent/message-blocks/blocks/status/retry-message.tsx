import { Button, Flex, Text, Tooltip } from "@radix-ui/themes";
import { RotateCw, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { AgentMessage } from "@/lib/agent.types";

import { formatElapsedDuration } from "../../shared/message-duration";
import { MessageCardShell } from "../../shared/message-shell";

import "./status-message.css";

interface RetryMessageProps {
  message: AgentMessage;
  onAbort?: () => void;
}

function getRetryCount(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : fallback;
}

function getRetryInMs(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : null;
}

function useRetryCountdown(retryInMs: number | null): number | null {
  const [remainingMs, setRemainingMs] = useState<number | null>(retryInMs);

  useEffect(() => {
    if (retryInMs === null) {
      setRemainingMs(null);
      return undefined;
    }
    setRemainingMs(retryInMs);
    const startedAt = Date.now();
    const interval = window.setInterval(() => {
      const next = retryInMs - (Date.now() - startedAt);
      if (next <= 1000) {
        window.clearInterval(interval);
        setRemainingMs(1000);
      } else {
        setRemainingMs(next);
      }
    }, 200);
    return () => window.clearInterval(interval);
  }, [retryInMs]);

  return remainingMs;
}

function useRetryElapsed(): number {
  const startRef = useRef<number>(Date.now());
  const [now, setNow] = useState<number>(Date.now());

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(interval);
  }, []);

  return now - startRef.current;
}

export function RetryMessage({ message, onAbort }: RetryMessageProps) {
  const { t } = useTranslation();
  const attempt = getRetryCount(message.payload?.attempt, 1);
  const maxAttempts = getRetryCount(message.payload?.max_attempts, attempt);
  const detail = message.content?.trim() || t("assistant.upstreamFailure");
  const remainingMs = useRetryCountdown(getRetryInMs(message.payload?.retry_in_ms));
  const remainingSeconds = remainingMs === null ? null : Math.ceil(remainingMs / 1000);
  const elapsedMs = useRetryElapsed();

  return (
    <MessageCardShell className="agent-status-message-card">
      <Flex
        direction="column"
        gap="1"
      >
        <Flex
          align="center"
          gap="2"
          className="agent-status-message-header"
        >
          <RotateCw
            size={16}
            className="agent-status-message-icon"
            data-status-tone="retry"
          />
          <Text
            size="2"
            weight="medium"
            className="agent-status-message-title"
            data-status-tone="retry"
          >
            {t("assistant.retryProgress", { attempt, max: maxAttempts })}
          </Text>
          <Text
            size="1"
            color="gray"
            className="agent-retry-timer"
          >
            {formatElapsedDuration(elapsedMs)}
            {remainingSeconds !== null
              ? ` (${t("assistant.retryCountdown", { seconds: remainingSeconds })})`
              : null}
          </Text>
          {onAbort ? (
            <Button
              size="1"
              variant="soft"
              color="gray"
              className="agent-retry-cancel-button"
              onClick={onAbort}
            >
              <X size={12} />
              {t("assistant.cancelRetry")}
            </Button>
          ) : null}
        </Flex>
        <Flex
          align="start"
          gap="1"
          className="agent-status-message-detail"
        >
          <Text
            size="1"
            color="gray"
            className="agent-retry-error-prefix"
          >
            {t("assistant.retryErrorPrefix")}
          </Text>
          <Tooltip content={detail}>
            <Text
              size="1"
              color="gray"
              className="agent-retry-error-text"
            >
              {detail}
            </Text>
          </Tooltip>
        </Flex>
      </Flex>
    </MessageCardShell>
  );
}
