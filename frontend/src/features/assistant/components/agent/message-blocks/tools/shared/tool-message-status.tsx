import { ToolBody, ToolNotice, ToolTextBlock } from "./tool-message-shared";
import i18n from "@/i18n";

interface ToolErrorMessageProps {
  errorMessage: string;
}

interface UnregisteredToolMessageProps {
  toolName?: string;
  errorMessage?: string;
}

export function ToolErrorMessage({ errorMessage }: ToolErrorMessageProps) {
  return (
    <ToolBody>
      <ToolNotice title={i18n.t("assistant.tools.toolError")} tone="error">
        {errorMessage}
      </ToolNotice>
    </ToolBody>
  );
}

export function UnregisteredToolMessage({
  toolName,
  errorMessage,
}: UnregisteredToolMessageProps) {
  return (
    <ToolBody>
      <ToolNotice title={i18n.t("assistant.tools.unregisteredTool")} tone="warning">
        {i18n.t("assistant.tools.unregisteredToolDescription")}
      </ToolNotice>
      <ToolTextBlock label={i18n.t("assistant.tools.toolName")} value={toolName ?? i18n.t("assistant.tools.unknown")} />
      <ToolTextBlock label={i18n.t("assistant.tools.description")} value={errorMessage} />
    </ToolBody>
  );
}
