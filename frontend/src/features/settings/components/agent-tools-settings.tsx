/**
 * Agent Tools Settings Component
 *
 * Agent 工具权限设置面板。
 */

import { Box, Flex, Text } from "@radix-ui/themes";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { LabeledSelect, type SelectOption } from "@/components/select";

import type { AgentToolMetadata, AgentToolPermissionMode, Settings } from "../lib/settings.types";

interface AgentToolsSettingsProps {
  settings: Settings;
  tools: AgentToolMetadata[];
  errorMessage?: string;
  onSettingsChange: (settings: Settings) => void;
  isSaving?: boolean;
}

const PERMISSION_OPTIONS: AgentToolPermissionMode[] = ["allow", "ask", "deny"];

const TOOL_DISPLAY_KEYS: Record<string, { name: string; description: string }> = {
  ask_user: {
    name: "settings.agentTool.askUser.name",
    description: "settings.agentTool.askUser.description",
  },
  write_plan: {
    name: "settings.agentTool.writePlan.name",
    description: "settings.agentTool.writePlan.description",
  },
  read_chapter: {
    name: "settings.agentTool.readChapter.name",
    description: "settings.agentTool.readChapter.description",
  },
  search_chapters: {
    name: "settings.agentTool.searchChapters.name",
    description: "settings.agentTool.searchChapters.description",
  },
  update_index: {
    name: "settings.agentTool.updateIndex.name",
    description: "settings.agentTool.updateIndex.description",
  },
  list_chapters: {
    name: "settings.agentTool.listChapters.name",
    description: "settings.agentTool.listChapters.description",
  },
  list_volumes: {
    name: "settings.agentTool.listVolumes.name",
    description: "settings.agentTool.listVolumes.description",
  },
  read_chapter_summaries: {
    name: "settings.agentTool.readChapterSummaries.name",
    description: "settings.agentTool.readChapterSummaries.description",
  },
  read_range_summaries: {
    name: "settings.agentTool.readRangeSummaries.name",
    description: "settings.agentTool.readRangeSummaries.description",
  },
  write_chapter: {
    name: "settings.agentTool.writeChapter.name",
    description: "settings.agentTool.writeChapter.description",
  },
  edit_chapter: {
    name: "settings.agentTool.editChapter.name",
    description: "settings.agentTool.editChapter.description",
  },
  delete_chapter: {
    name: "settings.agentTool.deleteChapter.name",
    description: "settings.agentTool.deleteChapter.description",
  },
  create_volume: {
    name: "settings.agentTool.createVolume.name",
    description: "settings.agentTool.createVolume.description",
  },
  edit_volume: {
    name: "settings.agentTool.editVolume.name",
    description: "settings.agentTool.editVolume.description",
  },
  delete_volume: {
    name: "settings.agentTool.deleteVolume.name",
    description: "settings.agentTool.deleteVolume.description",
  },
  move_chapter_to_volume: {
    name: "settings.agentTool.moveChapterToVolume.name",
    description: "settings.agentTool.moveChapterToVolume.description",
  },
  list_notes: {
    name: "settings.agentTool.listNotes.name",
    description: "settings.agentTool.listNotes.description",
  },
  read_note: {
    name: "settings.agentTool.readNote.name",
    description: "settings.agentTool.readNote.description",
  },
  write_note: {
    name: "settings.agentTool.writeNote.name",
    description: "settings.agentTool.writeNote.description",
  },
  edit_note: {
    name: "settings.agentTool.editNote.name",
    description: "settings.agentTool.editNote.description",
  },
  delete_note: {
    name: "settings.agentTool.deleteNote.name",
    description: "settings.agentTool.deleteNote.description",
  },
  move_note: {
    name: "settings.agentTool.moveNote.name",
    description: "settings.agentTool.moveNote.description",
  },
  create_note_category: {
    name: "settings.agentTool.createNoteCategory.name",
    description: "settings.agentTool.createNoteCategory.description",
  },
  edit_note_category: {
    name: "settings.agentTool.editNoteCategory.name",
    description: "settings.agentTool.editNoteCategory.description",
  },
  delete_note_category: {
    name: "settings.agentTool.deleteNoteCategory.name",
    description: "settings.agentTool.deleteNoteCategory.description",
  },
  list_characters: {
    name: "settings.agentTool.listCharacters.name",
    description: "settings.agentTool.listCharacters.description",
  },
  read_character: {
    name: "settings.agentTool.readCharacter.name",
    description: "settings.agentTool.readCharacter.description",
  },
  create_character: {
    name: "settings.agentTool.createCharacter.name",
    description: "settings.agentTool.createCharacter.description",
  },
  edit_character: {
    name: "settings.agentTool.editCharacter.name",
    description: "settings.agentTool.editCharacter.description",
  },
  delete_character: {
    name: "settings.agentTool.deleteCharacter.name",
    description: "settings.agentTool.deleteCharacter.description",
  },
  list_world_entries: {
    name: "settings.agentTool.listWorldEntries.name",
    description: "settings.agentTool.listWorldEntries.description",
  },
  read_world_entry: {
    name: "settings.agentTool.readWorldEntry.name",
    description: "settings.agentTool.readWorldEntry.description",
  },
  create_world_entry: {
    name: "settings.agentTool.createWorldEntry.name",
    description: "settings.agentTool.createWorldEntry.description",
  },
  edit_world_entry: {
    name: "settings.agentTool.editWorldEntry.name",
    description: "settings.agentTool.editWorldEntry.description",
  },
  delete_world_entry: {
    name: "settings.agentTool.deleteWorldEntry.name",
    description: "settings.agentTool.deleteWorldEntry.description",
  },
  dispatch_subagent: {
    name: "settings.agentTool.dispatchSubagent.name",
    description: "settings.agentTool.dispatchSubagent.description",
  },
  notify_subagent: {
    name: "settings.agentTool.notifySubagent.name",
    description: "settings.agentTool.notifySubagent.description",
  },
  recycle_subagent: {
    name: "settings.agentTool.recycleSubagent.name",
    description: "settings.agentTool.recycleSubagent.description",
  },
  activate_skill: {
    name: "settings.agentTool.activateSkill.name",
    description: "settings.agentTool.activateSkill.description",
  },
  reference_skill: {
    name: "settings.agentTool.referenceSkill.name",
    description: "settings.agentTool.referenceSkill.description",
  },
};

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
    [t],
  );

  const permissionMap = useMemo(
    () => new Map(settings.agentToolPermissions.map((item) => [item.toolName, item.mode])),
    [settings.agentToolPermissions],
  );
  const displayTools = useMemo(() => tools.filter((tool) => TOOL_DISPLAY_KEYS[tool.key]), [tools]);

  const handlePermissionChange = (toolName: string, mode: string) => {
    const nextMode = mode as AgentToolPermissionMode;
    const nextPermissions = settings.agentToolPermissions.map((item) => ({
      ...item,
      mode: item.toolName === toolName ? nextMode : item.mode,
    }));

    onSettingsChange({
      ...settings,
      agentToolPermissions: nextPermissions,
    });
  };

  return (
    <Box>
      <Flex
        direction="column"
        gap="4"
      >
        <Text
          size="2"
          color="gray"
        >
          {t("settings.agentToolsDescription")}
        </Text>

        {errorMessage ? (
          <Text
            size="2"
            color="red"
          >
            {errorMessage}
          </Text>
        ) : null}

        {!errorMessage && displayTools.length === 0 ? (
          <Text
            size="2"
            color="gray"
          >
            {t("settings.agentToolsEmpty")}
          </Text>
        ) : null}

        <Flex
          direction="column"
          gap="2"
        >
          {displayTools.map((tool) => (
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
              <Flex
                direction="column"
                gap="1"
                style={{ minWidth: 0, flex: 1 }}
              >
                <Text
                  size="2"
                  weight="medium"
                >
                  {t(TOOL_DISPLAY_KEYS[tool.key].name)}
                </Text>
                <Text
                  size="2"
                  color="gray"
                  style={{ lineHeight: 1.5 }}
                >
                  {t(TOOL_DISPLAY_KEYS[tool.key].description)}
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
