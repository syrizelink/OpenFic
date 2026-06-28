import { Box, Flex, Text } from "@radix-ui/themes";
import { HelpCircle } from "lucide-react";

import type { AgentQuestionSpecialPanel } from "../../agent-special-panels-state";
import {
  ClarificationQuestionActions,
  ClarificationQuestionBody,
} from "../messages/special/clarification-question-flow";
import { getClarificationPromptKey, type ClarificationPromptData } from "../messages/special/clarification-flow-state";
import { useClarificationQuestionFlow } from "../messages/special/use-clarification-question-flow";
import { SpecialPanelShell } from "./special-panel-shell";

interface ClarificationSpecialPanelProps {
  panel: AgentQuestionSpecialPanel;
  onSubmitQuestionAnswer?: (actionId: string, answer: string) => void;
  readOnly?: boolean;
}

export function ClarificationSpecialPanel({
  panel,
  onSubmitQuestionAnswer,
  readOnly = false,
}: ClarificationSpecialPanelProps) {
  return (
    <ClarificationSpecialPanelContent
      key={getClarificationPromptKey(panel.prompt)}
      prompt={panel.prompt}
      summary={panel.summary}
      readOnly={readOnly}
      onSubmitQuestionAnswer={onSubmitQuestionAnswer}
    />
  );
}

interface ClarificationSpecialPanelContentProps {
  prompt: ClarificationPromptData;
  summary: string;
  onSubmitQuestionAnswer?: (actionId: string, answer: string) => void;
  readOnly?: boolean;
}

function ClarificationSpecialPanelContent({
  prompt,
  summary,
  onSubmitQuestionAnswer,
  readOnly = false,
}: ClarificationSpecialPanelContentProps) {
  const model = useClarificationQuestionFlow(prompt, { onSubmitQuestionAnswer });
  const content = readOnly ? (
    <Flex direction="column" gap="3">
      {prompt.questions.map((question, index) => (
        <Box key={`${question.title}-${index}`}>
          <Text size="2" weight="medium">
            {index + 1}. {question.title}
          </Text>
          {question.description ? (
            <Text size="1" color="gray" style={{ display: "block", marginTop: "4px" }}>
              {question.description}
            </Text>
          ) : null}
          {question.options.length > 0 ? (
            <Flex direction="column" gap="1" mt="2">
              {question.options.map((option) => (
                <Text key={option.label} size="1" color="gray">
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
      title="需要补充信息"
      summary={summary}
      content={content}
      actions={readOnly ? undefined : <ClarificationQuestionActions model={model} />}
    />
  );
}
