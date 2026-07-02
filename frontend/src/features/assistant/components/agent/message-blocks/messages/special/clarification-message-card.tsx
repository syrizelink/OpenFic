import { Box, Flex, Text } from "@radix-ui/themes";
import { AlertCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { AgentMessage } from "../../../../../../../lib/agent.types";
import { MessageCardShell } from "../../shared/message-shell";
import {
  ClarificationQuestionActions,
  ClarificationQuestionBody,
} from "./clarification-question-flow";
import {
  getClarificationPromptData,
  getClarificationPromptKey,
  type ClarificationPromptData,
} from "./clarification-flow-state";
import { useClarificationQuestionFlow } from "./use-clarification-question-flow";

interface ClarificationMessageCardProps {
  message: Pick<AgentMessage, "questions" | "payload" | "correlationId">;
  onSubmitQuestionAnswer?: (actionId: string, answer: string) => void;
}

export function ClarificationMessageCard({
  message,
  onSubmitQuestionAnswer,
}: ClarificationMessageCardProps) {
  const prompt = getClarificationPromptData(message);

  if (prompt.questions.length === 0) return null;

  return (
    <ClarificationMessageCardContent
      key={getClarificationPromptKey(prompt)}
      prompt={prompt}
      onSubmitQuestionAnswer={onSubmitQuestionAnswer}
    />
  );
}

interface ClarificationMessageCardContentProps {
  prompt: ClarificationPromptData;
  onSubmitQuestionAnswer?: (actionId: string, answer: string) => void;
}

function ClarificationMessageCardContent({
  prompt,
  onSubmitQuestionAnswer,
}: ClarificationMessageCardContentProps) {
  const { t } = useTranslation();
  const model = useClarificationQuestionFlow(prompt, { onSubmitQuestionAnswer });

  return (
    <MessageCardShell>
      <Flex align="center" gap="2" style={{ marginBottom: "12px" }}>
        <AlertCircle size={16} style={{ color: "var(--gray-11)" }} />
        <Text size="2" weight="medium" style={{ color: "var(--gray-12)" }}>
          {t("assistant.clarificationCardTitle")}
        </Text>
      </Flex>
      <ClarificationQuestionBody model={model} bodyClassName="agent-question-panel-body" />
      {(model.shouldStep || model.canRenderSubmit) && (
        <Box mt="3">
          <ClarificationQuestionActions model={model} />
        </Box>
      )}
    </MessageCardShell>
  );
}
