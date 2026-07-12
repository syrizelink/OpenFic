import { Flex, Text } from "@radix-ui/themes";
import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";

interface AgentSettingsLockNoticeProps {
  isLocked: boolean;
}

export function AgentSettingsLockNotice({ isLocked }: AgentSettingsLockNoticeProps) {
  const { t } = useTranslation();

  if (!isLocked) return null;

  return (
    <Flex
      align="start"
      gap="3"
      role="status"
      className="settings-dialog-lock-notice"
    >
      <AlertTriangle
        size={17}
        strokeWidth={2}
        className="settings-dialog-lock-notice-icon"
        aria-hidden="true"
      />
      <Text
        size="2"
        className="settings-dialog-lock-notice-copy"
      >
        {t("settings.agentSettingsLocked")} {t("settings.agentSettingsLockHint")}
      </Text>
    </Flex>
  );
}
