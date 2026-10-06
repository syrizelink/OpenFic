/**
 * General Settings Component
 *
 * 通用设置面板，包含语言、明暗模式、字体设置。
 */

import { Box, Flex, Text } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";

import { StepperNumberInput } from "@/components";
import { LabeledSelect } from "@/components/select";
import { supportedLanguages, type LanguageCode } from "@/i18n";

import type { Settings } from "../lib/settings.types";
import { getCodeFontOptions, getFontOptions, type ThemeMode } from "../lib/settings.types";

interface GeneralSettingsProps {
  /** 当前设置 */
  settings: Settings;
  /** 设置变更回调 */
  onSettingsChange: (settings: Settings) => void;
  isSaving?: boolean;
}

interface FontSizeFieldProps {
  label: string;
  value: number;
  onCommit: (value: number) => void;
  disabled?: boolean;
}

const MIN_FONT_SIZE = 10;
const MAX_FONT_SIZE = 28;

function FontSizeField({ label, value, onCommit, disabled = false }: FontSizeFieldProps) {
  const { t } = useTranslation();

  return (
    <Flex
      direction="column"
      gap="2"
    >
      <Text
        size="2"
        weight="medium"
        color="gray"
      >
        {label}
      </Text>
      <StepperNumberInput
        value={value}
        min={MIN_FONT_SIZE}
        max={MAX_FONT_SIZE}
        unit="px"
        width={200}
        increaseAriaLabel={t("settings.increaseFontSize")}
        decreaseAriaLabel={t("settings.decreaseFontSize")}
        onCommit={onCommit}
        disabled={disabled}
      />
    </Flex>
  );
}

export function GeneralSettings({
  settings,
  onSettingsChange,
  isSaving = false,
}: GeneralSettingsProps) {
  const { t } = useTranslation();

  /** 更新语言 */
  const handleLanguageChange = (language: string) => {
    onSettingsChange({ ...settings, language: language as LanguageCode });
  };

  /** 更新字体 */
  const handleFontChange = (fontFamily: string) => {
    onSettingsChange({ ...settings, fontFamily });
  };

  /** 更新代码字体 */
  const handleCodeFontChange = (codeFontFamily: string) => {
    onSettingsChange({ ...settings, codeFontFamily });
  };

  /** 更新基础字号 */
  const handleBaseFontSizeCommit = (value: number) => {
    onSettingsChange({ ...settings, baseFontSize: value });
  };

  /** 更新编辑器字号 */
  const handleEditorFontSizeCommit = (value: number) => {
    onSettingsChange({ ...settings, editorFontSize: value });
  };

  return (
    <Box>
      <Flex
        direction="column"
        gap="4"
      >
        {/* 语言设置 */}
        <LabeledSelect
          label={t("settings.language")}
          labelColor="gray"
          value={settings.language}
          options={supportedLanguages.map((lang) => ({
            value: lang.code,
            label: lang.name,
          }))}
          onChange={handleLanguageChange}
          disabled={isSaving}
          triggerStyle={{ width: 200 }}
        />

        <LabeledSelect
          label={t("settings.theme")}
          labelColor="gray"
          value={settings.theme}
          options={[
            { value: "system", label: t("settings.themeSystem") },
            { value: "light", label: t("settings.themeLight") },
            { value: "dark", label: t("settings.themeDark") },
          ]}
          onChange={(value) => onSettingsChange({ ...settings, theme: value as ThemeMode })}
          disabled={isSaving}
          triggerStyle={{ width: 200 }}
        />

        {/* 字体设置 */}
        <LabeledSelect
          label={t("settings.fontFamily")}
          labelColor="gray"
          value={settings.fontFamily}
          options={getFontOptions(t)}
          onChange={handleFontChange}
          disabled={isSaving}
          triggerStyle={{ width: 200 }}
        />

        {/* 代码字体设置 */}
        <LabeledSelect
          label={t("settings.codeFontFamily")}
          labelColor="gray"
          value={settings.codeFontFamily || "JetBrains Mono Variable"}
          options={getCodeFontOptions(t)}
          onChange={handleCodeFontChange}
          disabled={isSaving}
          triggerStyle={{ width: 200 }}
        />

        {/* 基础字号设置 */}
        <FontSizeField
          label={t("settings.baseFontSize")}
          value={settings.baseFontSize}
          onCommit={handleBaseFontSizeCommit}
          disabled={isSaving}
        />

        {/* 编辑器字号设置 */}
        <FontSizeField
          label={t("settings.editorFontSize")}
          value={settings.editorFontSize}
          onCommit={handleEditorFontSizeCommit}
          disabled={isSaving}
        />
      </Flex>
    </Box>
  );
}
