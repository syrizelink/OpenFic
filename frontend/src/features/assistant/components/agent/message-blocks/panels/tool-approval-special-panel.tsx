import { Button } from "@radix-ui/themes";
import { ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { AgentApprovalSpecialPanel } from "../../agent-special-panels-state";
import type { AgentSpecialPanel } from "../../agent-special-panels-state";
import { SpecialPanelShell } from "./special-panel-shell";

interface ToolApprovalSpecialPanelProps {
  panel: AgentApprovalSpecialPanel;
  onApproveTool?: (approvalId: string, approved: boolean) => void;
  onBatchDecision?: (panel: AgentSpecialPanel, decision: { approved: boolean }) => void;
  readOnly?: boolean;
}

export function ToolApprovalSpecialPanel({
  panel,
  onApproveTool,
  onBatchDecision,
  readOnly = false,
}: ToolApprovalSpecialPanelProps) {
  const { t } = useTranslation();
  void readOnly;
  return (
    <SpecialPanelShell
      kind="approval"
      icon={<ShieldAlert size={15} />}
      title={t("assistant.specialPanels.approvalTitle")}
      summary={panel.summary}
      progress={
        panel.batchIndex !== undefined && panel.batchTotal !== undefined
          ? `${panel.batchIndex + 1}/${panel.batchTotal}`
          : undefined
      }
      actions={
        !onApproveTool && !onBatchDecision ? undefined : (
          <>
            <Button
              size="1"
              variant="soft"
              color="gray"
              onClick={() =>
                onBatchDecision
                  ? onBatchDecision(panel, { approved: false })
                  : onApproveTool?.(panel.approval.approval_id, false)
              }
            >
              {t("assistant.specialPanels.deny")}
            </Button>
            <Button
              size="1"
              onClick={() =>
                onBatchDecision
                  ? onBatchDecision(panel, { approved: true })
                  : onApproveTool?.(panel.approval.approval_id, true)
              }
            >
              {t("assistant.specialPanels.approve")}
            </Button>
          </>
        )
      }
    />
  );
}
