import { Button, Flex, Switch, Text } from "@radix-ui/themes";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { toast } from "@/components";
import { showSystemNotification } from "@/lib/system-notification";

import type { Settings } from "../lib/settings.types";

const notificationEvents = [
  {
    key: "notifyOnCompletion",
    labelKey: "settings.notificationPreference.completed",
    hintKey: "settings.notificationPreference.completedHint",
  },
  {
    key: "notifyOnApproval",
    labelKey: "settings.notificationPreference.approval",
    hintKey: "settings.notificationPreference.approvalHint",
  },
  {
    key: "notifyOnQuestion",
    labelKey: "settings.notificationPreference.question",
    hintKey: "settings.notificationPreference.questionHint",
  },
  {
    key: "notifyOnError",
    labelKey: "settings.notificationPreference.error",
    hintKey: "settings.notificationPreference.errorHint",
  },
] as const;

interface NotificationSettingsProps {
  settings: Settings;
  isSaving: boolean;
  onSettingsChange: (settings: Settings) => void;
}

export function NotificationSettings({
  settings,
  isSaving,
  onSettingsChange,
}: NotificationSettingsProps) {
  const { t } = useTranslation();
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">(() =>
    typeof Notification === "undefined" ? "unsupported" : Notification.permission,
  );

  const requestPermission = async () => {
    if (typeof Notification === "undefined") {
      setPermission("unsupported");
      return false;
    }
    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      return result === "granted";
    } catch {
      setPermission("denied");
      return false;
    }
  };

  const handleCheckedChange = async (checked: boolean) => {
    if (!checked || (await requestPermission())) {
      onSettingsChange({ ...settings, notificationsEnabled: checked });
    }
  };

  const handleTestNotification = async () => {
    if (!(await requestPermission())) return;
    try {
      showSystemNotification(
        t("settings.notificationsTestTitle"),
        t("settings.notificationsTestBody"),
      );
    } catch {
      toast.error(t("settings.notificationsTestFailed"));
    }
  };

  return (
    <Flex
      direction="column"
      gap="3"
    >
      <Flex
        align="center"
        justify="between"
        gap="4"
      >
        <Flex
          direction="column"
          gap="1"
        >
          <Text
            size="2"
            weight="medium"
          >
            {t("settings.notificationsEnabled")}
          </Text>
          <Text
            size="1"
            color="gray"
          >
            {t("settings.notificationsHint")}
          </Text>
        </Flex>
        <Switch
          checked={settings.notificationsEnabled}
          disabled={isSaving || permission === "unsupported"}
          aria-label={t("settings.notificationsEnabled")}
          onCheckedChange={(checked) => void handleCheckedChange(checked)}
        />
      </Flex>
      {permission === "denied" || permission === "unsupported" ? (
        <Text
          size="1"
          color="red"
        >
          {t(
            permission === "denied"
              ? "settings.notificationsDenied"
              : "settings.notificationsUnsupported",
          )}
        </Text>
      ) : null}
      {notificationEvents.map(({ key, labelKey, hintKey }) => (
        <Flex
          key={key}
          align="center"
          justify="between"
          gap="4"
        >
          <Flex
            direction="column"
            gap="1"
          >
            <Text
              size="2"
              weight="medium"
            >
              {t(labelKey)}
            </Text>
            <Text
              size="1"
              color="gray"
            >
              {t(hintKey)}
            </Text>
          </Flex>
          <Switch
            checked={settings[key]}
            disabled={isSaving}
            aria-label={t(labelKey)}
            onCheckedChange={(checked) => onSettingsChange({ ...settings, [key]: checked })}
          />
        </Flex>
      ))}
      <Flex
        align="center"
        justify="between"
        gap="4"
      >
        <Flex
          direction="column"
          gap="1"
        >
          <Text
            size="2"
            weight="medium"
          >
            {t("settings.notificationsOnlyWhenUnfocused")}
          </Text>
          <Text
            size="1"
            color="gray"
          >
            {t("settings.notificationsOnlyWhenUnfocusedHint")}
          </Text>
        </Flex>
        <Switch
          checked={settings.notifyOnlyWhenUnfocused}
          disabled={isSaving}
          aria-label={t("settings.notificationsOnlyWhenUnfocused")}
          onCheckedChange={(checked) =>
            onSettingsChange({ ...settings, notifyOnlyWhenUnfocused: checked })
          }
        />
      </Flex>
      <Flex
        align="center"
        justify="between"
        gap="4"
      >
        <Flex
          direction="column"
          gap="1"
        >
          <Text
            size="2"
            weight="medium"
          >
            {t("settings.notificationsTest")}
          </Text>
          <Text
            size="1"
            color="gray"
          >
            {t("settings.notificationsTestHint")}
          </Text>
        </Flex>
        <Button
          variant="soft"
          disabled={permission === "unsupported"}
          onClick={() => void handleTestNotification()}
        >
          {t("settings.notificationsTestAction")}
        </Button>
      </Flex>
    </Flex>
  );
}
