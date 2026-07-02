import type { AgentMessage } from "@/lib/agent.types";
import i18n from "@/i18n";

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
          <ToolTextBlock label={i18n.t("assistant.tools.action")} value={actionLabel} />
          <ToolTextBlock label={i18n.t("assistant.tools.skill")} value={name ?? skillId} />
          <ToolTextBlock label="Skill ID" value={name && skillId ? skillId : undefined} />
          <ToolTextBlock label={i18n.t("assistant.tools.reason")} value={reason} />
          <ToolTextBlock label={i18n.t("assistant.tools.result")} value={resultMessage} />
        </>
      ) : (
        <ToolNotice title={emptyTitle}>
          {i18n.t("assistant.tools.skillNoStructuredContent")}
        </ToolNotice>
      )}
    </ToolBody>
  );
}
