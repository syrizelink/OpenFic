import { Box } from "@radix-ui/themes";

import type { AgentMessage } from "@/lib/agent.types";

import { ToolBody } from "../shared/tool-message-shared";
import { getSubagentInstructionText } from "./subagent-tool-message-utils";
import "./subagent-tool-message.css";

interface DispatchSubagentToolMessageBodyProps {
  message: AgentMessage;
}

export function DispatchSubagentToolMessageBody({
  message,
}: DispatchSubagentToolMessageBodyProps) {
  const task = getSubagentInstructionText(message, ["task"]);
  if (!task) return null;
  return (
    <ToolBody>
      <Box className="agent-subagent-tool-callout">
        <Box className="agent-tool-block-content agent-subagent-tool-callout-content">
          <Box className="agent-subagent-tool-callout-label">已根据指令委派：</Box>
          <Box className="agent-subagent-tool-callout-prompt agent-tool-content-plain-text">{task}</Box>
        </Box>
      </Box>
    </ToolBody>
  );
}
