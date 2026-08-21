import { Flex } from "@radix-ui/themes";

import { type AgentSpecialPanel, getAgentSpecialPanelVariant } from "./agent-special-panels-state";
import type { ClarificationAnswerItem } from "./message-blocks/messages/special/clarification-flow-state";
import { ClarificationSpecialPanel } from "./message-blocks/panels/clarification-special-panel";
import { ToolApprovalSpecialPanel } from "./message-blocks/panels/tool-approval-special-panel";

interface AgentSpecialPanelsProps {
  panels: AgentSpecialPanel[];
  embedded?: boolean;
  onApproveTool?: (approvalId: string, approved: boolean) => void;
  onSubmitQuestionAnswer?: (actionId: string, answer: ClarificationAnswerItem[]) => void;
  onSkipQuestion?: (actionId: string) => void;
  onBatchDecision?: (
    panel: AgentSpecialPanel,
    decision: { approved?: boolean; answer?: ClarificationAnswerItem[] },
  ) => void;
  readOnly?: boolean;
}

export function AgentSpecialPanels({
  panels,
  embedded = false,
  onApproveTool,
  onSubmitQuestionAnswer,
  onSkipQuestion,
  onBatchDecision,
  readOnly = false,
}: AgentSpecialPanelsProps) {
  const variant = getAgentSpecialPanelVariant(embedded);

  if (panels.length === 0) return null;
  const batchPanels = panels.filter((panel) => panel.batchId);
  const visiblePanels = batchPanels.length > 0 ? batchPanels.slice(0, 1) : panels.slice(0, 1);

  return (
    <Flex
      direction="column-reverse"
      gap="2"
      className="agent-special-panel-stack"
      data-embedded={embedded ? "true" : "false"}
      data-variant={variant}
      style={{
        gridArea: embedded ? "auto" : "stack",
        alignSelf: embedded ? "stretch" : "end",
        width: "100%",
        position: "relative",
        zIndex: 0,
        pointerEvents: embedded ? "auto" : "none",
        filter: embedded ? "none" : undefined,
      }}
    >
      {visiblePanels.map((panel) => {
        if (panel.kind === "question") {
          return (
            <ClarificationSpecialPanel
              key={panel.id}
              panel={panel}
              readOnly={readOnly}
              onSubmitQuestionAnswer={onSubmitQuestionAnswer}
              onSkipQuestion={onSkipQuestion}
              onBatchDecision={panel.batchId ? onBatchDecision : undefined}
            />
          );
        }

        return (
          <ToolApprovalSpecialPanel
            key={panel.id}
            panel={panel}
            readOnly={readOnly}
            onApproveTool={onApproveTool}
            onBatchDecision={panel.batchId ? onBatchDecision : undefined}
          />
        );
      })}
    </Flex>
  );
}
