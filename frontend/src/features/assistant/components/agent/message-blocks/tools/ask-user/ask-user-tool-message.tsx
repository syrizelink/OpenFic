import { Box, Flex, Text } from "@radix-ui/themes";

import i18n from "@/i18n";
import type { AgentMessage } from "@/lib/agent.types";

import "./ask-user-tool-message.css";

import { ToolBody } from "../shared/tool-message-shared";
import { getAskUserQuestionAnswerPairs } from "../shared/tool-message-utils";

interface AskUserToolMessageProps {
  message: AgentMessage;
}

export function AskUserToolMessage({ message }: AskUserToolMessageProps) {
  if (message.status !== "completed") return null;
  const pairs = getAskUserQuestionAnswerPairs(message);
  if (pairs.length === 0) return null;

  return (
    <ToolBody>
      <Box className="agent-ask-user-panel">
        <Flex
          align="center"
          justify="between"
          gap="3"
          className="agent-ask-user-panel-header"
        >
          <Text className="agent-ask-user-panel-title">{i18n.t("assistant.tools.askUser")}</Text>
          <Text className="agent-ask-user-panel-count">
            {i18n.t("assistant.tools.questionCount", { count: pairs.length })}
          </Text>
        </Flex>
        <ol className="agent-ask-user-list">
          {pairs.map((pair, index) => {
            const promptText = pair.description ?? pair.question;

            return (
              <li
                key={`${pair.question}-${index}`}
                className="agent-ask-user-item"
              >
                <span className="agent-ask-user-index">{index + 1}</span>
                <Box className="agent-ask-user-item-main">
                  <Text className="agent-ask-user-item-title">{promptText}</Text>
                  <Box className="agent-ask-user-answer-block">
                    <Box className="agent-ask-user-answer-value agent-tool-content-plain-text">
                      {pair.answer}
                    </Box>
                  </Box>
                </Box>
              </li>
            );
          })}
        </ol>
      </Box>
    </ToolBody>
  );
}
