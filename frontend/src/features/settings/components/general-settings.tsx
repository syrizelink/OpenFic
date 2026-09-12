/**
 * General Settings Component
 *
 * Panel pengaturan umum, memuat pengaturan bahasa, tema, dan fon.
 */

import { Box, Flex, Text, TextField, SegmentedControl } from "@radix-ui/themes";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { LabeledSelect } from "@/components/select";
import { supportedLanguages, type LanguageCode } from "@/i18n";

import type { Settings, ThemeMode } from "../lib/settings.types";
import { getCodeFontOptions, getFontOptions } from "../lib/settings.types";

interface GeneralSettingsProps {
  /** Pengaturan saat ini */
  settings: Settings;
  /** Callback perubahan pengaturan */
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
  isSaving = false,
}: GeneralSettingsProps) {
  const { t } = useTranslation();

  /** Memperbarui bahasa */
  const handleLanguageChange = (language: string) => {
    onSettingsChange({ ...settings, language: language as LanguageCode });
  };

  /** Memperbarui tema */
  const handleThemeChange = (theme: string) => {
    onSettingsChange({ ...settings, theme: theme as ThemeMode });
  };

  /** Memperbarui fon */
  const handleFontChange = (fontFamily: string) => {
    onSettingsChange({ ...settings, fontFamily });
  };

  /** Memperbarui fon kode */
  const handleCodeFontChange = (codeFontFamily: string) => {
    onSettingsChange({ ...settings, codeFontFamily });
  };

  /** Memperbarui ukuran fon dasar */
  const handleBaseFontSizeCommit = (value: number) => {
    onSettingsChange({ ...settings, baseFontSize: value });
  };

  /** Memperbarui ukuran fon editor */
  const handleEditorFontSizeCommit = (value: number) => {
    onSettingsChange({ ...settings, editorFontSize: value });
  };

  return (
    <Box>
      <Flex
        direction="column"
        gap="4"
      >
        {/* Pengaturan bahasa */}
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

        {/* Pengaturan tema */}
        <Flex
          direction="column"
          gap="2"
        >
          <Text
            size="2"
            weight="medium"
            color="gray"
          >
            {t("settings.theme")}
          </Text>
          <SegmentedControl.Root
            value={settings.theme}
            onValueChange={handleThemeChange}
            disabled={isSaving}
            style={{ width: 200 }}
          >
            <SegmentedControl.Item value="light">{t("settings.themeLight")}</SegmentedControl.Item>
            <SegmentedControl.Item value="dark">{t("settings.themeDark")}</SegmentedControl.Item>
          </SegmentedControl.Root>
        </Flex>

        {/* Pengaturan fon */}
        <LabeledSelect
          label={t("settings.fontFamily")}
          labelColor="gray"
          value={settings.fontFamily}
          options={getFontOptions(t)}
          onChange={handleFontChange}
          disabled={isSaving}
          triggerStyle={{ width: 200 }}
        />

        {/* Pengaturan fon kode */}
        <LabeledSelect
          label={t("settings.codeFontFamily")}
          labelColor="gray"
          value={settings.codeFontFamily || "JetBrains Mono Variable"}
          options={getCodeFontOptions(t)}
          onChange={handleCodeFontChange}
          disabled={isSaving}
          triggerStyle={{ width: 200 }}
        />

        {/* Pengaturan ukuran fon dasar */}
        <FontSizeField
          label={t("settings.baseFontSize")}
          value={settings.baseFontSize}
          onCommit={handleBaseFontSizeCommit}
          disabled={isSaving}
        />

        {/* Pengaturan ukuran fon editor */}
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
