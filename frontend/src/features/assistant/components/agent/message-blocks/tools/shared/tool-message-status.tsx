import { ToolBody, ToolNotice, ToolTextBlock } from "./tool-message-shared";

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
      <ToolNotice title="工具调用失败" tone="error">
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
      <ToolNotice title="未注册工具" tone="warning">
        当前前端没有为这条工具消息注册显式渲染器。
      </ToolNotice>
      <ToolTextBlock label="工具名" value={toolName ?? "未知"} />
      <ToolTextBlock label="说明" value={errorMessage} />
    </ToolBody>
  );
}
