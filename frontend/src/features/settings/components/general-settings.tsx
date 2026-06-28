/**
 * General Settings Component
 *
 * 通用设置面板，包含语言、主题、字体设置。
 */

import { Box, Flex, Text, SegmentedControl } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";

import type { Settings, ThemeMode } from "../lib/settings.types";
import { FONT_OPTIONS, CODE_FONT_OPTIONS } from "../lib/settings.types";
import { supportedLanguages, type LanguageCode } from "@/i18n";
import { LabeledSelect } from "@/components/select";

interface GeneralSettingsProps {
  /** 当前设置 */
  settings: Settings;
  /** 设置变更回调 */
  onSettingsChange: (settings: Settings) => void;
}

export function GeneralSettings({
  settings,
  onSettingsChange,
}: GeneralSettingsProps) {
  const { t } = useTranslation();

  /** 更新语言 */
  const handleLanguageChange = (language: string) => {
    onSettingsChange({ ...settings, language: language as LanguageCode });
  };

  /** 更新主题 */
  const handleThemeChange = (theme: string) => {
    onSettingsChange({ ...settings, theme: theme as ThemeMode });
  };

  /** 更新字体 */
  const handleFontChange = (fontFamily: string) => {
    onSettingsChange({ ...settings, fontFamily });
  };

  /** 更新代码字体 */
  const handleCodeFontChange = (codeFontFamily: string) => {
    onSettingsChange({ ...settings, codeFontFamily });
  };

  return (
    <Box>
      <Flex direction="column" gap="4">
        {/* 语言设置 */}
        <LabeledSelect
          label={t("settings.language")}
          value={settings.language}
          options={supportedLanguages.map((lang) => ({
            value: lang.code,
            label: lang.name,
          }))}
          onChange={handleLanguageChange}
          triggerStyle={{ width: 200 }}
        />

        {/* 主题设置 */}
        <Flex direction="column" gap="2">
          <Text size="2" weight="medium" color="gray">
            {t("settings.theme")}
          </Text>
          <SegmentedControl.Root
            value={settings.theme}
            onValueChange={handleThemeChange}
            style={{ width: 200 }}
          >
            <SegmentedControl.Item value="light">
              {t("settings.themeLight")}
            </SegmentedControl.Item>
            <SegmentedControl.Item value="dark">
              {t("settings.themeDark")}
            </SegmentedControl.Item>
          </SegmentedControl.Root>
        </Flex>

        {/* 字体设置 */}
        <LabeledSelect
          label={t("settings.fontFamily")}
          value={settings.fontFamily}
          options={FONT_OPTIONS}
          onChange={handleFontChange}
          triggerStyle={{ width: 200 }}
        />

        {/* 代码字体设置 */}
        <LabeledSelect
          label={t("settings.codeFontFamily")}
          value={settings.codeFontFamily || "JetBrainsMapleMono"}
          options={CODE_FONT_OPTIONS}
          onChange={handleCodeFontChange}
          triggerStyle={{ width: 200 }}
        />
      </Flex>
    </Box>
  );
}
