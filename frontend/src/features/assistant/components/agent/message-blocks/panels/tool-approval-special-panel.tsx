import { Button } from "@radix-ui/themes";
import { ShieldAlert } from "lucide-react";

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
  void readOnly;
  return (
    <SpecialPanelShell
      kind="approval"
      icon={<ShieldAlert size={15} />}
      title="需要审批"
      summary={panel.summary}
      actions={!onApproveTool
        ? undefined
        : (
          <>
            <Button size="1" variant="soft" color="gray" onClick={() => onApproveTool(panel.approval.approval_id, false)}>
              拒绝
            </Button>
            <Button size="1" onClick={() => onApproveTool(panel.approval.approval_id, true)}>
              执行
            </Button>
          </>
        )}
    />
  );
}
