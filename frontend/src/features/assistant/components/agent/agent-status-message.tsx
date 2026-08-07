import { Box, Flex } from "@radix-ui/themes";

interface AgentStatusMessageProps {
  content: string;
}

export function AgentStatusMessage({ content }: AgentStatusMessageProps) {
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
      </Flex>
    </Box>
  );
}
