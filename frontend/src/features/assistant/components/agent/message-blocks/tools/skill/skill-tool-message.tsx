import type { AgentMessage } from "@/lib/agent.types";

import {
  asString,
  getStreamingData,
  getToolResultMessage,
} from "../shared/tool-message-utils";
import {
  ToolBody,
  ToolNotice,
  ToolTextBlock,
} from "../shared/tool-message-shared";

interface SkillToolMessageProps {
  message: AgentMessage;
  actionLabel: string;
  emptyTitle: string;
}

export function SkillToolMessage({
  message,
  actionLabel,
  emptyTitle,
}: SkillToolMessageProps) {
  const data = getStreamingData(message);
  const name = asString(data.name);
  const skillId = asString(data.skill_id);
  const reason = asString(data.reason);
  const resultMessage = getToolResultMessage(message);
  const hasStructuredContent = Boolean(name || skillId || reason || resultMessage);

  return (
    <ToolBody>
      {hasStructuredContent ? (
        <>
          <ToolTextBlock label="操作" value={actionLabel} />
          <ToolTextBlock label="技能" value={name ?? skillId} />
          <ToolTextBlock label="Skill ID" value={name && skillId ? skillId : undefined} />
          <ToolTextBlock label="原因" value={reason} />
          <ToolTextBlock label="结果" value={resultMessage} />
        </>
      ) : (
        <ToolNotice title={emptyTitle}>
          这条技能工具消息没有返回可显示的结构化内容。
        </ToolNotice>
      )}
    </ToolBody>
  );
}
