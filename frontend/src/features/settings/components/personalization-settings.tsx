import { Box, Button, Flex, Text } from "@radix-ui/themes";
import { useEffect, useId, useRef, useState, type ChangeEvent } from "react";
import { HexColorInput, HexColorPicker } from "react-colorful";
import { useTranslation } from "react-i18next";

import { toast } from "@/components";
import { LabeledSelect, type SelectOption } from "@/components/select";
import {
  CUSTOM_THEME_PRESET,
  CUSTOM_THEME_PRESET_ID,
  createThemeExport,
  getThemePresetLabelKey,
  getThemePresetsForAppearance,
  parseThemeExport,
  resolveThemeConfig,
  type ThemeAppearance,
  type ThemeConfig,
  type ThemePalette,
  type ThemePresetId,
  type ThemeSettings,
} from "@/lib/theme";

import type { Settings } from "../lib/settings.types";

import "./personalization-settings.css";

interface PersonalizationSettingsProps {
  settings: Settings;
  onSettingsChange: (settings: Settings) => void;
  onThemePreviewChange: (settings: ThemeSettings) => void;
  isSaving?: boolean;
}

type ThemeColorKey = "accent" | "gray" | "background";

interface ThemeColorRowProps {
  label: string;
  value: string;
  disabled: boolean;
  onCommit: (value: string) => void;
  onPreview: (value: string) => void;
}

const HEX_COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/;

function ThemeColorRow({ label, value, disabled, onCommit, onPreview }: ThemeColorRowProps) {
  const [draftValue, setDraftValue] = useState(value);
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const pickerRef = useRef<HTMLSpanElement>(null);
  const committedValueRef = useRef(value);
  const pickerId = useId();

  useEffect(() => {
    setDraftValue(value);
    committedValueRef.current = value;
  }, [value]);

  useEffect(() => {
    if (!isPickerOpen) return;

    const handlePointerDown = (event: PointerEvent) => {
      if (pickerRef.current?.contains(event.target as Node)) return;
      if (draftValue !== committedValueRef.current) {
        committedValueRef.current = draftValue;
        onCommit(draftValue);
      }
      setIsPickerOpen(false);
    };

    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [draftValue, isPickerOpen, onCommit]);

  const restoreCommitted = () => {
    const nextValue = committedValueRef.current;
    setDraftValue(nextValue);
    onPreview(nextValue);
  };

  const commit = (nextValue = draftValue) => {
    if (!HEX_COLOR_PATTERN.test(nextValue)) {
      restoreCommitted();
      return;
    }
    if (nextValue === committedValueRef.current) return;
    committedValueRef.current = nextValue;
    onCommit(nextValue);
  };

  const reset = () => {
    restoreCommitted();
    setIsPickerOpen(false);
  };

  const handleColorChange = (nextValue: string) => {
    setDraftValue(nextValue);
    if (HEX_COLOR_PATTERN.test(nextValue)) onPreview(nextValue);
  };

  const handleColorInputBlur = () => commit();

  const handleSwatchClick = () => {
    if (isPickerOpen) {
      commit();
      setIsPickerOpen(false);
      return;
    }
    setIsPickerOpen(true);
  };

  return (
    <div
      className="theme-setting-row"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          reset();
        } else if (event.key === "Enter" && isPickerOpen) {
          commit();
        }
      }}
    >
      <span className="theme-setting-row-label">{label}</span>
      <span
        ref={pickerRef}
        className="theme-setting-color-control"
      >
        <button
          type="button"
          className="theme-setting-color-swatch"
          aria-label={label}
          aria-controls={pickerId}
          aria-expanded={isPickerOpen}
          aria-haspopup="dialog"
          disabled={disabled}
          style={{ backgroundColor: draftValue }}
          onClick={handleSwatchClick}
        />
        <HexColorInput
          color={draftValue}
          prefixed
          aria-label={label}
          disabled={disabled}
          className="theme-setting-color-input"
          onChange={handleColorChange}
          onBlur={handleColorInputBlur}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.currentTarget.blur();
            if (event.key === "Escape") {
              event.stopPropagation();
              reset();
            }
          }}
        />
        {isPickerOpen ? (
          <span
            id={pickerId}
            className="theme-color-picker-popover"
            role="dialog"
            aria-label={label}
          >
            <HexColorPicker
              color={HEX_COLOR_PATTERN.test(draftValue) ? draftValue : committedValueRef.current}
              onChange={handleColorChange}
              onChangeEnd={commit}
            />
          </span>
        ) : null}
      </span>
    </div>
  );
}

function ThemePresetOptionIcon({
  presetId,
  appearance,
}: {
  presetId: string;
  appearance: ThemeAppearance;
}) {
  return (
    <span
      className="theme-preset-option-icon"
      data-theme-option={presetId}
      data-theme-appearance={appearance}
      aria-hidden="true"
    >
      Aa
    </span>
  );
}

interface ThemeModeSectionProps {
  appearance: ThemeAppearance;
  presetId: ThemePresetId;
  palette: ThemePalette;
  presetOptions: SelectOption[];
  disabled: boolean;
  onPresetChange: (appearance: ThemeAppearance, presetId: ThemePresetId) => void;
  onColorChange: (appearance: ThemeAppearance, key: ThemeColorKey, value: string) => void;
  onColorPreview: (appearance: ThemeAppearance, key: ThemeColorKey, value: string) => void;
}

function ThemeModeSection({
  appearance,
  presetId,
  palette,
  presetOptions,
  disabled,
  onPresetChange,
  onColorChange,
  onColorPreview,
}: ThemeModeSectionProps) {
  const { t } = useTranslation();
  const isDark = appearance === "dark";
  const title = t(isDark ? "settings.themeDarkTheme" : "settings.themeLightTheme");

  return (
    <Box
      className="theme-mode-section"
      data-theme-appearance={appearance}
    >
      <Flex
        align="center"
        justify="between"
        className="theme-mode-section-header"
      >
        <Text
          size="2"
          weight="medium"
        >
          {title}
        </Text>
        <LabeledSelect
          value={presetId}
          options={presetOptions}
          onChange={(value) => onPresetChange(appearance, value as ThemePresetId)}
          disabled={disabled}
          triggerClassName="theme-preset-select-trigger"
          triggerAriaLabel={title}
        />
      </Flex>
      <Flex
        direction="column"
        className="theme-mode-section-rows"
      >
        <ThemeColorRow
          label={t("settings.themeColorAccent")}
          value={palette.accent}
          disabled={disabled}
          onCommit={(value) => onColorChange(appearance, "accent", value)}
          onPreview={(value) => onColorPreview(appearance, "accent", value)}
        />
        <ThemeColorRow
          label={t("settings.themeColorBackground")}
          value={palette.background}
          disabled={disabled}
          onCommit={(value) => onColorChange(appearance, "background", value)}
          onPreview={(value) => onColorPreview(appearance, "background", value)}
        />
        <ThemeColorRow
          label={t("settings.themeColorGray")}
          value={palette.gray}
          disabled={disabled}
          onCommit={(value) => onColorChange(appearance, "gray", value)}
          onPreview={(value) => onColorPreview(appearance, "gray", value)}
        />
      </Flex>
    </Box>
  );
}

export function PersonalizationSettings({
  settings,
  onSettingsChange,
  onThemePreviewChange,
  isSaving = false,
}: PersonalizationSettingsProps) {
  const { t } = useTranslation();
  const themeFileInputRef = useRef<HTMLInputElement>(null);

  const handleThemePresetChange = (appearance: ThemeAppearance, themePreset: ThemePresetId) => {
    const nextLightThemePreset = appearance === "light" ? themePreset : settings.lightThemePreset;
    const nextDarkThemePreset = appearance === "dark" ? themePreset : settings.darkThemePreset;

    onSettingsChange({
      ...settings,
      themePreset: settings.theme === "dark" ? nextDarkThemePreset : nextLightThemePreset,
      lightThemePreset: nextLightThemePreset,
      darkThemePreset: nextDarkThemePreset,
      themeConfig: settings.themeConfig,
    });
  };

  const buildThemeConfigChange = (
    appearance: ThemeAppearance,
    key: ThemeColorKey,
    value: string,
  ): Settings => {
    const currentPreset =
      appearance === "light" ? settings.lightThemePreset : settings.darkThemePreset;
    const currentThemeConfig: ThemeConfig = {
      ...settings.themeConfig,
      [appearance]: resolveThemeConfig(currentPreset, settings.themeConfig)[appearance],
    };
    const nextLightThemePreset =
      appearance === "light" ? CUSTOM_THEME_PRESET_ID : settings.lightThemePreset;
    const nextDarkThemePreset =
      appearance === "dark" ? CUSTOM_THEME_PRESET_ID : settings.darkThemePreset;
    const nextPalette: ThemePalette = {
      ...currentThemeConfig[appearance],
      [key]: value,
    };
    delete nextPalette.variables;
    const nextThemeConfig: ThemeConfig = {
      ...currentThemeConfig,
      [appearance]: nextPalette,
    };

    return {
      ...settings,
      themePreset: settings.theme === "dark" ? nextDarkThemePreset : nextLightThemePreset,
      lightThemePreset: nextLightThemePreset,
      darkThemePreset: nextDarkThemePreset,
      themeConfig: nextThemeConfig,
    };
  };

  const handleThemeConfigChange = (
    appearance: ThemeAppearance,
    key: ThemeColorKey,
    value: string,
  ) => {
    onSettingsChange(buildThemeConfigChange(appearance, key, value));
  };

  const handleThemeConfigPreview = (
    appearance: ThemeAppearance,
    key: ThemeColorKey,
    value: string,
  ) => {
    onThemePreviewChange(buildThemeConfigChange(appearance, key, value));
  };

  const handleThemeExport = () => {
    const content = JSON.stringify(createThemeExport(settings), null, 2);
    const blob = new Blob([content], { type: "application/json" });
    const downloadUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = downloadUrl;
    anchor.download = "openfic-theme.json";
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 0);
  };

  const handleThemeImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (!selectedFile || isSaving) return;

    const isJsonFile =
      selectedFile.type === "application/json" || selectedFile.name.toLowerCase().endsWith(".json");
    if (!isJsonFile) {
      toast.error(t("settings.themeImportInvalidFileType"));
      return;
    }

    try {
      const importedTheme = parseThemeExport(JSON.parse(await selectedFile.text()) as unknown);
      if (!importedTheme) {
        toast.error(t("settings.themeImportInvalidFile"));
        return;
      }

      onSettingsChange({
        ...settings,
        themePreset: CUSTOM_THEME_PRESET_ID,
        lightThemePreset: CUSTOM_THEME_PRESET_ID,
        darkThemePreset: CUSTOM_THEME_PRESET_ID,
        themeConfig: importedTheme,
      });
    } catch {
      toast.error(t("settings.themeImportInvalidFile"));
    }
  };

  const buildThemePresetOptions = (appearance: ThemeAppearance): SelectOption[] =>
    [...getThemePresetsForAppearance(appearance), CUSTOM_THEME_PRESET].map((preset) => ({
      value: preset.id,
      label: t(getThemePresetLabelKey(preset, appearance)),
      prefix: (
        <ThemePresetOptionIcon
          presetId={preset.id}
          appearance={appearance}
        />
      ),
    }));
  const themePresetOptions = {
    light: buildThemePresetOptions("light"),
    dark: buildThemePresetOptions("dark"),
  };
  const resolvedThemeConfig = {
    light: resolveThemeConfig(settings.lightThemePreset, settings.themeConfig).light,
    dark: resolveThemeConfig(settings.darkThemePreset, settings.themeConfig).dark,
  };

  return (
    <Box>
      <Flex
        direction="column"
        gap="5"
        className="theme-settings-section"
      >
        <Flex
          direction="column"
          gap="3"
        >
          <ThemeModeSection
            appearance="light"
            presetId={settings.lightThemePreset}
            palette={resolvedThemeConfig.light}
            presetOptions={themePresetOptions.light}
            disabled={isSaving}
            onPresetChange={handleThemePresetChange}
            onColorChange={handleThemeConfigChange}
            onColorPreview={handleThemeConfigPreview}
          />
          <ThemeModeSection
            appearance="dark"
            presetId={settings.darkThemePreset}
            palette={resolvedThemeConfig.dark}
            presetOptions={themePresetOptions.dark}
            disabled={isSaving}
            onPresetChange={handleThemePresetChange}
            onColorChange={handleThemeConfigChange}
            onColorPreview={handleThemeConfigPreview}
          />
        </Flex>
        <Flex
          direction="column"
          gap="5"
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
                {t("settings.themeExport")}
              </Text>
              <Text
                size="1"
                color="gray"
              >
                {t("settings.themeExportHint")}
              </Text>
            </Flex>
            <Button
              variant="soft"
              disabled={isSaving}
              onClick={handleThemeExport}
            >
              {t("settings.themeExportButton")}
            </Button>
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
                {t("settings.themeImport")}
              </Text>
              <Text
                size="1"
                color="gray"
              >
                {t("settings.themeImportHint")}
              </Text>
            </Flex>
            <Button
              variant="soft"
              disabled={isSaving}
              onClick={() => themeFileInputRef.current?.click()}
            >
              {t("settings.themeImportButton")}
            </Button>
          </Flex>
        </Flex>
      </Flex>
      <input
        ref={themeFileInputRef}
        className="theme-file-input"
        type="file"
        accept=".json,application/json"
        onChange={(event) => void handleThemeImport(event)}
      />
    </Box>
  );
}
