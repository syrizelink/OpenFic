import { Box, Button, Flex, Text } from "@radix-ui/themes";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { ClarificationQuestion } from "../../../../../../../lib/agent.types";
import { CUSTOM_CLARIFICATION_ANSWER } from "./clarification-flow-state";
import type { ClarificationQuestionFlowModel } from "./use-clarification-question-flow";

interface ClarificationQuestionBodyProps {
  bodyClassName?: string;
  model: ClarificationQuestionFlowModel;
}

interface ClarificationQuestionActionsProps {
  model: ClarificationQuestionFlowModel;
}

export function ClarificationQuestionBody({
  model,
  bodyClassName,
}: ClarificationQuestionBodyProps) {
  const { t } = useTranslation();
  const { prompt } = model;
  if (prompt.questions.length === 0) return null;

  const content = model.shouldStep ? (
    <>
      <Flex
        className="agent-clarification-stepper"
        aria-label={t("assistant.clarification.progress")}
      >
        {prompt.questions.map((question, index) => (
          <span
            key={`${question.title}-${index}`}
            className="agent-clarification-stepper-dot"
            data-active={index === model.currentStep}
          />
        ))}
      </Flex>
      <ClarificationQuestionItem
        question={prompt.questions[model.currentStep]}
        index={model.currentStep}
        selectedValue={model.answers[model.currentStep]}
        customValue={model.customAnswers[model.currentStep] ?? ""}
        onSelect={model.handleSelectAnswer}
        onCustomChange={model.handleCustomAnswerChange}
      />
    </>
  ) : (
    <>
      {prompt.questions.map((question, index) => (
        <ClarificationQuestionItem
          key={`${question.title}-${index}`}
          question={question}
          index={index}
          selectedValue={model.answers[index]}
          customValue={model.customAnswers[index] ?? ""}
          onSelect={model.handleSelectAnswer}
          onCustomChange={model.handleCustomAnswerChange}
        />
      ))}
      <Text
        size="1"
        style={{
          display: "block",
          color: "var(--gray-10)",
          marginTop: "12px",
          fontStyle: "italic",
        }}
      >
        {t("assistant.clarification.multiSelectHint")}
      </Text>
    </>
  );

  return bodyClassName ? <Box className={bodyClassName}>{content}</Box> : content;
}

export function ClarificationQuestionActions({ model }: ClarificationQuestionActionsProps) {
  const { t } = useTranslation();
  const { prompt } = model;
  if (prompt.questions.length === 0) return null;

  if (model.shouldStep) {
    return (
      <Flex
        align="center"
        justify="between"
        style={{ width: "100%" }}
      >
        <Text
          size="1"
          color="gray"
        >
          {model.currentStep + 1} / {prompt.questions.length}
        </Text>
        <Flex gap="2">
          {model.currentStep > 0 && (
            <Button
              size="1"
              variant="soft"
              onClick={model.handlePrev}
            >
              <ChevronLeft size={14} />
              {t("assistant.clarification.previous")}
            </Button>
          )}
          {!model.isLastStep ? (
            <Button
              size="1"
              onClick={model.handleNext}
              disabled={!model.isCurrentStepValid}
            >
              {t("assistant.clarification.next")}
              <ChevronRight size={14} />
            </Button>
          ) : (
            model.canRenderSubmit && (
              <Button
                size="1"
                onClick={model.handleSubmit}
                disabled={!model.canSubmit}
              >
                {t("assistant.clarification.submit")}
              </Button>
            )
          )}
        </Flex>
      </Flex>
    );
  }

  if (!model.canRenderSubmit) return null;

  return (
    <Flex justify="end">
      <Button
        size="1"
        onClick={model.handleSubmit}
        disabled={!model.canSubmit}
      >
        {t("assistant.clarification.submit")}
      </Button>
    </Flex>
  );
}

interface ClarificationQuestionItemProps {
  customValue: string;
  index: number;
  question: ClarificationQuestion;
  selectedValue?: string;
  onCustomChange: (index: number, value: string) => void;
  onSelect: (index: number, value: string) => void;
}

function ClarificationQuestionItem({
  customValue,
  index,
  question,
  selectedValue,
  onCustomChange,
  onSelect,
}: ClarificationQuestionItemProps) {
  const { t } = useTranslation();
  const options = [
    ...question.options.map((option) => ({
      ...option,
      value: option.label,
    })),
    {
      label: t("assistant.clarification.customInput"),
      description: t("assistant.clarification.customInputDescription"),
      value: CUSTOM_CLARIFICATION_ANSWER,
    },
  ];

  return (
    <fieldset className="agent-clarification-question">
      <legend className="agent-clarification-question-title">
        {index + 1}. {question.title}
      </legend>
      {question.description && (
        <Text
          size="1"
          color="gray"
          className="agent-clarification-question-description"
        >
          {question.description}
        </Text>
      )}
      <Flex
        direction="column"
        gap="2"
        mt="2"
      >
        {options.map((option) => {
          const inputId = `clarification-${index}-${option.value}`;

          return (
            <label
              key={option.value}
              className="agent-clarification-option"
              htmlFor={inputId}
            >
              <input
                id={inputId}
                type="radio"
                name={`clarification-${index}`}
                value={option.value}
                checked={selectedValue === option.value}
                onChange={() => onSelect(index, option.value)}
              />
              <span className="agent-clarification-option-copy">
                <span className="agent-clarification-option-label">{option.label}</span>
                {option.description && (
                  <span className="agent-clarification-option-description">
                    {option.description}
                  </span>
                )}
              </span>
            </label>
          );
        })}
      </Flex>
      {selectedValue === CUSTOM_CLARIFICATION_ANSWER && (
        <textarea
          className="ai-sidebar-textarea agent-clarification-custom-input"
          value={customValue}
          onChange={(event) => onCustomChange(index, event.target.value)}
          rows={2}
          placeholder={t("assistant.clarification.customInputPlaceholder")}
          aria-label={t("assistant.clarification.customAnswerAriaLabel", { title: question.title })}
        />
      )}
    </fieldset>
  );
}
