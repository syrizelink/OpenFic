import type { AgentMessage, ClarificationQuestion } from "../../../../../../../lib/agent.types";

export const CUSTOM_CLARIFICATION_ANSWER = "__custom__";

export type ClarificationAnswers = Record<number, string>;
export type ClarificationCustomAnswers = Record<number, string>;

export interface ClarificationPromptData {
  actionId: string;
  questions: ClarificationQuestion[];
}

type ClarificationMessageSource = Pick<AgentMessage, "questions" | "payload" | "correlationId">;

export function getClarificationPromptData(
  message: ClarificationMessageSource,
): ClarificationPromptData {
  const actionId =
    typeof message.payload?.action_id === "string"
      ? message.payload.action_id
      : (message.correlationId ?? "");

  return {
    actionId,
    questions: message.questions ?? [],
  };
}

export function getClarificationPromptKey(prompt: ClarificationPromptData): string {
  const questionSignature = prompt.questions
    .map((question) => `${question.title}:${question.options.length}`)
    .join("|");

  return `${prompt.actionId}:${questionSignature}`;
}

function resolveClarificationAnswer(
  answers: ClarificationAnswers,
  customAnswers: ClarificationCustomAnswers,
  index: number,
): string | undefined {
  const selected = answers[index];
  if (!selected) return undefined;
  if (selected !== CUSTOM_CLARIFICATION_ANSWER) return selected;

  const customAnswer = customAnswers[index]?.trim();
  return customAnswer || undefined;
}

export function isClarificationStepComplete(
  questions: ClarificationQuestion[],
  answers: ClarificationAnswers,
  customAnswers: ClarificationCustomAnswers,
  stepIndex: number,
): boolean {
  if (!questions[stepIndex]) return false;
  return Boolean(resolveClarificationAnswer(answers, customAnswers, stepIndex));
}

export function canSubmitClarificationAnswers(
  questions: ClarificationQuestion[],
  answers: ClarificationAnswers,
  customAnswers: ClarificationCustomAnswers,
): boolean {
  if (questions.length === 0) return false;
  return questions.every((_, index) =>
    isClarificationStepComplete(questions, answers, customAnswers, index),
  );
}

export function buildClarificationAnswerText(
  questions: ClarificationQuestion[],
  answers: ClarificationAnswers,
  customAnswers: ClarificationCustomAnswers,
): string | null {
  if (!canSubmitClarificationAnswers(questions, answers, customAnswers)) return null;

  return questions
    .map((question, index) => {
      const answer = resolveClarificationAnswer(answers, customAnswers, index) ?? "";
      return `${index + 1}. ${question.title}\n${answer}`;
    })
    .join("\n\n");
}
