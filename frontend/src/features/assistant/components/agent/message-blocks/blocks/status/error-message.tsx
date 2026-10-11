import { Box, Flex, Text } from "@radix-ui/themes";
import { AlertCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { InfoTooltip } from "@/components";
import type { AgentMessage } from "@/lib/agent.types";

import { MessageCardShell } from "../../shared/message-shell";

import "./status-message.css";

interface ErrorMessageProps {
  message: AgentMessage;
}

export function ErrorMessage({ message }: ErrorMessageProps) {
  const { t } = useTranslation();
  const detail = message.content?.trim() || t("assistant.noErrorDetail");

  return (
    <MessageCardShell className="agent-status-message-card">
      <Flex
        align="center"
        gap="2"
        className="agent-status-message-header"
      >
        <InfoTooltip content={<Box className="agent-tool-error-tooltip">{detail}</Box>}>
          <Box
            className="agent-tool-error-indicator"
            role="img"
            aria-label={detail}
            tabIndex={0}
          >
            <AlertCircle
              size={16}
              className="agent-status-message-icon"
              data-status-tone="error"
            />
          </Box>
        </InfoTooltip>
        <Text
          size="2"
          weight="medium"
          className="agent-status-message-title"
          data-status-tone="error"
        >
          {t("assistant.errorTitle")}
        </Text>
      </Flex>
    </MessageCardShell>
  );
}
