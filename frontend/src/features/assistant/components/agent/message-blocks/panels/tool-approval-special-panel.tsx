import { Button } from "@radix-ui/themes";
import { ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { AgentApprovalSpecialPanel } from "../../agent-special-panels-state";
import { SpecialPanelShell } from "./special-panel-shell";

interface ToolApprovalSpecialPanelProps {
  panel: AgentApprovalSpecialPanel;
  onApproveTool?: (approvalId: string, approved: boolean) => void;
  readOnly?: boolean;
}

export function ToolApprovalSpecialPanel({
  panel,
  onApproveTool,
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
      actions={
        !onApproveTool ? undefined : (
          <>
            <Button
              size="1"
              variant="soft"
              color="gray"
              onClick={() => onApproveTool(panel.approval.approval_id, false)}
            >
              {t("assistant.specialPanels.deny")}
            </Button>
            <Button
              size="1"
              onClick={() => onApproveTool(panel.approval.approval_id, true)}
            >
              {t("assistant.specialPanels.approve")}
            </Button>
          </>
        )
      }
    />
  );
}
