import { Box, Flex, Text } from "@radix-ui/themes";
import { useEffect, useState } from "react";

import { formatElapsedDuration } from "./message-blocks/shared/message-duration";

interface AgentStatusMessageProps {
  content: string;
  startedAt?: number;
}

export function AgentStatusMessage({ content, startedAt }: AgentStatusMessageProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (startedAt === undefined) return;

    setNow(Date.now());
    const intervalId = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(intervalId);
  }, [startedAt]);

  const elapsedMs = startedAt === undefined ? null : Math.max(0, now - startedAt);

  return (
    <Box className="agent-message-card">
      <Flex
        align="center"
        gap="2"
        className="agent-status-message"
      >
        <span
          className="text-shimmer"
          data-text={content}
        >
          {content}
        </span>
        {elapsedMs !== null ? (
          <Text
            size="1"
            color="gray"
            className="agent-status-message-timer"
          >
            {formatElapsedDuration(elapsedMs)}
          </Text>
        ) : null}
      </Flex>
    </Box>
  );
}
