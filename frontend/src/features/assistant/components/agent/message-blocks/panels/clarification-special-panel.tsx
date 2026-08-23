import { Box, Button, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import { ChevronDown, ChevronUp, HelpCircle } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { AgentQuestionSpecialPanel } from "../../agent-special-panels-state";
import type { AgentSpecialPanel } from "../../agent-special-panels-state";
import {
  getClarificationPromptKey,
  type ClarificationAnswerItem,
  type ClarificationPromptData,
} from "../messages/special/clarification-flow-state";
import {
  ClarificationQuestionActions,
  ClarificationQuestionBody,
} from "../messages/special/clarification-question-flow";
import { useClarificationQuestionFlow } from "../messages/special/use-clarification-question-flow";
import { SpecialPanelShell } from "./special-panel-shell";

interface ClarificationSpecialPanelProps {
  panel: AgentQuestionSpecialPanel;
  onSubmitQuestionAnswer?: (actionId: string, answer: ClarificationAnswerItem[]) => void;
  onSkipQuestion?: (actionId: string) => void;
  onBatchDecision?: (
    panel: AgentSpecialPanel,
    decision: { answer?: ClarificationAnswerItem[]; skipped?: boolean },
  ) => void;
  readOnly?: boolean;
}

export function ClarificationSpecialPanel({
  panel,
  onSubmitQuestionAnswer,
  onSkipQuestion,
  onBatchDecision,
  readOnly = false,
}: ClarificationSpecialPanelProps) {
  return (
    <ClarificationSpecialPanelContent
      key={getClarificationPromptKey(panel.prompt)}
      panel={panel}
      prompt={panel.prompt}
      summary={panel.summary}
      readOnly={readOnly}
      onSubmitQuestionAnswer={onSubmitQuestionAnswer}
      onSkipQuestion={onSkipQuestion}
      onBatchDecision={onBatchDecision}
    />
  );
}

interface ClarificationSpecialPanelContentProps {
  panel: AgentQuestionSpecialPanel;
  prompt: ClarificationPromptData;
  summary: string;
  onSubmitQuestionAnswer?: (actionId: string, answer: ClarificationAnswerItem[]) => void;
  onSkipQuestion?: (actionId: string) => void;
  onBatchDecision?: (
    panel: AgentSpecialPanel,
    decision: { answer?: ClarificationAnswerItem[]; skipped?: boolean },
  ) => void;
  readOnly?: boolean;
}

function ClarificationSpecialPanelContent({
  panel,
  prompt,
  summary,
  onSubmitQuestionAnswer,
  onSkipQuestion,
  onBatchDecision,
  readOnly = false,
}: ClarificationSpecialPanelContentProps) {
  const { t } = useTranslation();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const hasQuestions = prompt.questions.length > 0;
  const model = useClarificationQuestionFlow(prompt, {
    onSubmitQuestionAnswer: (actionId, answer) => {
      if (onBatchDecision) {
        onBatchDecision(panel, { answer });
        return;
      }
      onSubmitQuestionAnswer?.(actionId, answer);
    },
  });
  const collapseLabel = isCollapsed
    ? t("assistant.specialPanels.expandQuestionPanel")
    : t("assistant.specialPanels.collapseQuestionPanel");
  const handleSkip = () => {
    if (onBatchDecision) {
      onBatchDecision(panel, { skipped: true });
      return;
    }
    onSkipQuestion?.(prompt.actionId);
  };
  const content = !hasQuestions ? (
    <Text
      size="2"
      color="red"
    >
      {t("assistant.specialPanels.invalidQuestion")}
    </Text>
  ) : readOnly ? (
    <Flex
      direction="column"
      gap="3"
    >
      {prompt.questions.map((question, index) => (
        <Box key={`${question.title}-${index}`}>
          <Text
            size="2"
            weight="medium"
          >
            {index + 1}. {question.title}
          </Text>
          {question.description ? (
            <Text
              size="1"
              color="gray"
              style={{ display: "block", marginTop: "4px" }}
            >
              {question.description}
            </Text>
          ) : null}
          {question.options.length > 0 ? (
            <Flex
              direction="column"
              gap="1"
              mt="2"
            >
              {question.options.map((option) => (
                <Text
                  key={option.label}
                  size="1"
                  color="gray"
                >
                  {option.label}
                </Text>
              ))}
            </Flex>
          ) : null}
        </Box>
      ))}
    </Flex>
  ) : (
    <Box className="agent-special-question-content">
      <ClarificationQuestionBody model={model} />
    </Box>
  );

  return (
    <SpecialPanelShell
      kind="question"
      icon={<HelpCircle size={15} />}
      title={t("assistant.specialPanels.clarificationTitle")}
      summary={summary}
      headingAction={
        <Tooltip content={collapseLabel}>
          <IconButton
            variant="ghost"
            color="gray"
            size="1"
            type="button"
            aria-label={collapseLabel}
            aria-expanded={!isCollapsed}
            onClick={() => setIsCollapsed((current) => !current)}
          >
            {isCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
          </IconButton>
        </Tooltip>
      }
      isCollapsed={isCollapsed}
      progress={
        panel.batchIndex !== undefined && panel.batchTotal !== undefined && panel.batchTotal > 1
          ? `${panel.batchIndex + 1}/${panel.batchTotal}`
          : undefined
      }
      content={content}
      actions={
        readOnly ? undefined : hasQuestions ? (
          <ClarificationQuestionActions
            model={model}
            leadingAction={
              <Button
                variant="ghost"
                color="gray"
                size="1"
                type="button"
                className="agent-clarification-skip-button"
                onClick={handleSkip}
              >
                {t("assistant.clarification.ignore")}
              </Button>
            }
          />
        ) : (
          <Button
            variant="ghost"
            color="gray"
            size="1"
            type="button"
            className="agent-clarification-skip-button"
            onClick={handleSkip}
          >
            {t("assistant.clarification.ignore")}
          </Button>
        )
      }
    />
  );
}
