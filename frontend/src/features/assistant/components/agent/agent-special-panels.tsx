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
  readOnly?: boolean;
}

export function AgentSpecialPanels({
  panels,
  embedded = false,
  onApproveTool,
  onSubmitQuestionAnswer,
  readOnly = false,
}: AgentSpecialPanelsProps) {
  const variant = getAgentSpecialPanelVariant(embedded);

  if (panels.length === 0) return null;
  const firstApprovalIndex = panels.findIndex((panel) => panel.kind === "approval");
  const visiblePanels = panels.filter(
    (panel, index) => panel.kind !== "approval" || index === firstApprovalIndex,
  );

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
            />
          );
        }

        return (
          <ToolApprovalSpecialPanel
            key={panel.id}
            panel={panel}
            readOnly={readOnly}
            onApproveTool={onApproveTool}
          />
        );
      })}
    </Flex>
  );
}
