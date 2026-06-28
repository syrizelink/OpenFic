import { Box } from "@radix-ui/themes";
import type { AgentMessage } from "@/lib/agent.types";

import { ToolBody } from "../shared/tool-message-shared";
import {
  getSubagentInstructionText,
} from "./subagent-tool-message-utils";
import "./subagent-tool-message.css";

interface NotifySubagentToolMessageProps {
  message: AgentMessage;
}

export function NotifySubagentToolMessage({ message }: NotifySubagentToolMessageProps) {
  const notifyMessage = getSubagentInstructionText(message, ["message"]);
  if (!notifyMessage) return null;
  return (
    <ToolBody>
      <Box className="agent-subagent-tool-callout">
        <Box className="agent-tool-block-content agent-subagent-tool-callout-content">
          <Box className="agent-subagent-tool-callout-label">已根据指令通知：</Box>
          <Box className="agent-subagent-tool-callout-prompt agent-tool-content-plain-text">
            {notifyMessage}
          </Box>
        </Box>
      </Box>
    </ToolBody>
  );
}
