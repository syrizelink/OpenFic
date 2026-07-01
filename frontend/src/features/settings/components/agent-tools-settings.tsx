/**
 * Agent Tools Settings Component
 *
 * Agent 工具权限设置面板。
 */

import { useMemo } from "react";
import { Box, Flex, Text } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";

import { LabeledSelect, type SelectOption } from "@/components/select";
import type {
  AgentToolMetadata,
  AgentToolPermissionMode,
  Settings,
} from "../lib/settings.types";

interface AgentToolsSettingsProps {
  settings: Settings;
  tools: AgentToolMetadata[];
  errorMessage?: string;
  onSettingsChange: (settings: Settings) => void;
  isSaving?: boolean;
}

const PERMISSION_OPTIONS: AgentToolPermissionMode[] = ["allow", "ask", "deny"];

export function AgentToolsSettings({
  settings,
  tools,
  errorMessage,
  onSettingsChange,
  isSaving = false,
}: AgentToolsSettingsProps) {
  const { t } = useTranslation();

  const permissionOptions = useMemo<SelectOption[]>(
    () =>
      PERMISSION_OPTIONS.map((mode) => ({
        value: mode,
        label: t(`settings.permission${mode[0].toUpperCase()}${mode.slice(1)}`),
      })),
    [t]
  );

  const permissionMap = useMemo(
    () => new Map(settings.agentToolPermissions.map((item) => [item.toolName, item.mode])),
    [settings.agentToolPermissions]
  );

  const handlePermissionChange = (toolName: string, mode: string) => {
    const nextMode = mode as AgentToolPermissionMode;
    const nextPermissions = tools.map((tool) => ({
      toolName: tool.key,
      mode: tool.key === toolName ? nextMode : permissionMap.get(tool.key) ?? "ask",
    }));

    onSettingsChange({
      ...settings,
      agentToolPermissions: nextPermissions,
    });
  };

  return (
    <Box>
      <Flex direction="column" gap="4">
        <Text size="2" color="gray">
          {t("settings.agentToolsDescription")}
        </Text>

        {errorMessage ? (
          <Text size="2" color="red">
            {errorMessage}
          </Text>
        ) : null}

        {!errorMessage && tools.length === 0 ? (
          <Text size="2" color="gray">
            {t("settings.agentToolsEmpty")}
          </Text>
        ) : null}

        <Flex direction="column" gap="2">
          {tools.map((tool) => (
            <Flex
              key={tool.key}
              align="center"
              justify="between"
              gap="4"
              style={{
                padding: "14px 16px",
                border: "1px solid var(--gray-a4)",
                borderRadius: "var(--radius-3)",
              }}
            >
              <Flex direction="column" gap="1" style={{ minWidth: 0, flex: 1 }}>
                <Text size="2" weight="medium">
                  {tool.name}
                </Text>
                <Text size="2" color="gray" style={{ lineHeight: 1.5 }}>
                  {tool.description}
                </Text>
              </Flex>

              <LabeledSelect
                value={permissionMap.get(tool.key) ?? "ask"}
                options={permissionOptions}
                onChange={(value) => handlePermissionChange(tool.key, value)}
                disabled={isSaving}
                triggerStyle={{ width: 120 }}
              />
            </Flex>
          ))}
        </Flex>
      </Flex>
    </Box>
  );
}
