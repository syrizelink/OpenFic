import { useState } from "react";

import {
  buildClarificationAnswerItems,
  canSubmitClarificationAnswers,
  isClarificationStepComplete,
  type ClarificationAnswers,
  type ClarificationAnswerItem,
  type ClarificationCustomAnswers,
  type ClarificationPromptData,
} from "./clarification-flow-state";

export interface ClarificationQuestionFlowModel {
  currentStep: number;
  customAnswers: ClarificationCustomAnswers;
  answers: ClarificationAnswers;
  isCurrentStepValid: boolean;
  isLastStep: boolean;
  canRenderSubmit: boolean;
  canSubmit: boolean;
  prompt: ClarificationPromptData;
  shouldStep: boolean;
  handleCustomAnswerChange: (index: number, value: string) => void;
  handleNext: () => void;
  handlePrev: () => void;
  handleSelectAnswer: (index: number, value: string) => void;
  handleSubmit: () => void;
}

interface UseClarificationQuestionFlowOptions {
  onSubmitQuestionAnswer?: (actionId: string, answer: ClarificationAnswerItem[]) => void;
}

export function useClarificationQuestionFlow(
  prompt: ClarificationPromptData,
  options: UseClarificationQuestionFlowOptions = {},
): ClarificationQuestionFlowModel {
  const { onSubmitQuestionAnswer } = options;
  const [answers, setAnswers] = useState<ClarificationAnswers>({});
  const [customAnswers, setCustomAnswers] = useState<ClarificationCustomAnswers>({});
  const [currentStep, setCurrentStep] = useState(0);

  const shouldStep = prompt.questions.length > 1;
  const canSubmit = canSubmitClarificationAnswers(prompt.questions, answers, customAnswers);
  const isCurrentStepValid = isClarificationStepComplete(
    prompt.questions,
    answers,
    customAnswers,
    currentStep,
  );
  const isLastStep = currentStep === prompt.questions.length - 1;

  const handleSubmit = () => {
    const answerItems = buildClarificationAnswerItems(prompt.questions, answers, customAnswers);
    if (!answerItems) return;

    onSubmitQuestionAnswer?.(prompt.actionId, answerItems);
    setAnswers({});
    setCustomAnswers({});
    setCurrentStep(0);
  };

  const handleSelectAnswer = (index: number, value: string) => {
    setAnswers((current) => ({ ...current, [index]: value }));
  };

  const handleCustomAnswerChange = (index: number, value: string) => {
    setCustomAnswers((current) => ({ ...current, [index]: value }));
  };

  const handleNext = () => {
    if (!isCurrentStepValid || currentStep >= prompt.questions.length - 1) return;
    setCurrentStep((step) => step + 1);
  };

  const handlePrev = () => {
    if (currentStep <= 0) return;
    setCurrentStep((step) => step - 1);
  };

  return {
    currentStep,
    customAnswers,
    answers,
    isCurrentStepValid,
    isLastStep,
    canRenderSubmit: Boolean(onSubmitQuestionAnswer),
    canSubmit,
    prompt,
    shouldStep,
    handleCustomAnswerChange,
    handleNext,
    handlePrev,
    handleSelectAnswer,
    handleSubmit,
  };
}
