/**
 * General Settings Component
 *
 * 通用设置面板，包含语言、主题、字体设置。
 */

import { Box, Flex, Text, TextField } from "@radix-ui/themes";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { HexColorInput, HexColorPicker } from "react-colorful";
import { useTranslation } from "react-i18next";

import { LabeledSelect, type SelectOption } from "@/components/select";
import { supportedLanguages, type LanguageCode } from "@/i18n";
import {
  CUSTOM_THEME_PRESET,
  CUSTOM_THEME_PRESET_ID,
  THEME_PRESETS,
  resolveThemeConfig,
  type ThemeAppearance,
  type ThemeConfig,
  type ThemePalette,
  type ThemePresetId,
  type ThemeSettings,
} from "@/lib/theme";

import type { Settings } from "../lib/settings.types";
import { getCodeFontOptions, getFontOptions } from "../lib/settings.types";

import "./general-settings.css";

interface GeneralSettingsProps {
  /** 当前设置 */
  settings: Settings;
  /** 设置变更回调 */
  onSettingsChange: (settings: Settings) => void;
  /** 主题临时预览回调，不触发设置保存 */
  onThemePreviewChange: (settings: ThemeSettings) => void;
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
const HEX_COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/;

interface ThemeColorRowProps {
  label: string;
  value: string;
  disabled: boolean;
  onCommit: (value: string) => void;
  onPreview: (value: string) => void;
}

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

function ThemePresetOptionIcon({ presetId }: { presetId: string }) {
  return (
    <span
      className="theme-preset-option-icon"
      data-theme-option={presetId}
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
  onColorChange: (appearance: ThemeAppearance, key: keyof ThemePalette, value: string) => void;
  onColorPreview: (appearance: ThemeAppearance, key: keyof ThemePalette, value: string) => void;
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
          label={t("settings.themeColorForeground")}
          value={palette.foreground}
          disabled={disabled}
          onCommit={(value) => onColorChange(appearance, "foreground", value)}
          onPreview={(value) => onColorPreview(appearance, "foreground", value)}
        />
      </Flex>
    </Box>
  );
}

function FontSizeField({ label, value, onCommit, disabled = false }: FontSizeFieldProps) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(() => String(value));
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDraft(String(value));
  }, [value]);

  const commit = () => {
    const parsed = Number(draft);
    if (Number.isNaN(parsed) || parsed <= 0) {
      setDraft(String(value));
      return;
    }
    const nextValue = Math.min(MAX_FONT_SIZE, Math.max(MIN_FONT_SIZE, Math.round(parsed)));
    if (nextValue === value) {
      setDraft(String(value));
      return;
    }
    onCommit(nextValue);
  };

  const stepBy = (delta: number) => {
    const base = Number.isFinite(Number(draft)) ? Number(draft) : value;
    const next = Math.min(MAX_FONT_SIZE, Math.max(MIN_FONT_SIZE, base + delta));
    setDraft(String(next));
    inputRef.current?.focus();
  };

  const stepperButton = (direction: "up" | "down") => {
    const isUp = direction === "up";
    return (
      <button
        type="button"
        tabIndex={-1}
        aria-label={isUp ? t("settings.increaseFontSize") : t("settings.decreaseFontSize")}
        disabled={disabled}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => stepBy(isUp ? 1 : -1)}
        className="font-size-stepper-btn"
      >
        {isUp ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
    );
  };

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
      <TextField.Root
        type="number"
        min={MIN_FONT_SIZE}
        max={MAX_FONT_SIZE}
        value={draft}
        ref={inputRef}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.currentTarget.blur();
          }
        }}
        disabled={disabled}
        className="font-size-field"
        style={{ width: 200 }}
      >
        <TextField.Slot
          side="right"
          className="font-size-stepper-slot"
        >
          <Flex
            direction="column"
            className="font-size-stepper"
          >
            {stepperButton("up")}
            {stepperButton("down")}
          </Flex>
        </TextField.Slot>
        <TextField.Slot side="right">px</TextField.Slot>
      </TextField.Root>
    </Flex>
  );
}

export function GeneralSettings({
  settings,
  onSettingsChange,
  onThemePreviewChange,
  isSaving = false,
}: GeneralSettingsProps) {
  const { t } = useTranslation();

  /** 更新语言 */
  const handleLanguageChange = (language: string) => {
    onSettingsChange({ ...settings, language: language as LanguageCode });
  };

  const handleThemePresetChange = (appearance: ThemeAppearance, themePreset: ThemePresetId) => {
    const preset = THEME_PRESETS.find((item) => item.id === themePreset);
    const currentPalette = resolveThemeConfig(
      appearance === "light" ? settings.lightThemePreset : settings.darkThemePreset,
      settings.themeConfig,
    )[appearance];
    const nextLightThemePreset = appearance === "light" ? themePreset : settings.lightThemePreset;
    const nextDarkThemePreset = appearance === "dark" ? themePreset : settings.darkThemePreset;
    const nextThemeConfig: ThemeConfig = {
      ...settings.themeConfig,
      [appearance]:
        themePreset === CUSTOM_THEME_PRESET_ID
          ? currentPalette
          : (preset?.[appearance] ?? currentPalette),
    };

    onSettingsChange({
      ...settings,
      themePreset: settings.theme === "dark" ? nextDarkThemePreset : nextLightThemePreset,
      lightThemePreset: nextLightThemePreset,
      darkThemePreset: nextDarkThemePreset,
      themeConfig: nextThemeConfig,
    });
  };

  const buildThemeConfigChange = (
    appearance: ThemeAppearance,
    key: keyof ThemePalette,
    value: string,
  ): Settings => {
    const currentThemeConfig: ThemeConfig = {
      light: resolveThemeConfig(settings.lightThemePreset, settings.themeConfig).light,
      dark: resolveThemeConfig(settings.darkThemePreset, settings.themeConfig).dark,
    };
    const nextLightThemePreset =
      appearance === "light" ? CUSTOM_THEME_PRESET_ID : settings.lightThemePreset;
    const nextDarkThemePreset =
      appearance === "dark" ? CUSTOM_THEME_PRESET_ID : settings.darkThemePreset;
    const nextThemeConfig: ThemeConfig = {
      ...currentThemeConfig,
      [appearance]: {
        ...currentThemeConfig[appearance],
        [key]: value,
      },
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
    key: keyof ThemePalette,
    value: string,
  ) => {
    onSettingsChange(buildThemeConfigChange(appearance, key, value));
  };

  const handleThemeConfigPreview = (
    appearance: ThemeAppearance,
    key: keyof ThemePalette,
    value: string,
  ) => {
    onThemePreviewChange(buildThemeConfigChange(appearance, key, value));
  };

  const themePresetOptions: SelectOption[] = [...THEME_PRESETS, CUSTOM_THEME_PRESET].map(
    (preset) => ({
      value: preset.id,
      label: t(preset.labelKey),
      prefix: <ThemePresetOptionIcon presetId={preset.id} />,
    }),
  );
  const resolvedThemeConfig = {
    light: resolveThemeConfig(settings.lightThemePreset, settings.themeConfig).light,
    dark: resolveThemeConfig(settings.darkThemePreset, settings.themeConfig).dark,
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

        <Flex
          direction="column"
          gap="3"
          className="theme-settings-section"
        >
          <ThemeModeSection
            appearance="light"
            presetId={settings.lightThemePreset}
            palette={resolvedThemeConfig.light}
            presetOptions={themePresetOptions}
            disabled={isSaving}
            onPresetChange={handleThemePresetChange}
            onColorChange={handleThemeConfigChange}
            onColorPreview={handleThemeConfigPreview}
          />
          <ThemeModeSection
            appearance="dark"
            presetId={settings.darkThemePreset}
            palette={resolvedThemeConfig.dark}
            presetOptions={themePresetOptions}
            disabled={isSaving}
            onPresetChange={handleThemePresetChange}
            onColorChange={handleThemeConfigChange}
            onColorPreview={handleThemeConfigPreview}
          />
        </Flex>

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
