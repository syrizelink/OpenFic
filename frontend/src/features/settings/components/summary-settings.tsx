import { Box, Button, Flex, Switch, Text } from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { ExternalLink } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import {
  ConfirmDialog,
  ModelIdSelect,
  Spinner,
  StepperNumberInput,
  toast,
  type ModelIdSelectOption,
} from "@/components";
import { useLlmModelOptions } from "@/lib/use-llm-model-options";

import {
  SYSTEM_DEFAULT_MODEL_REFERENCE,
  SYSTEM_LIGHT_MODEL_REFERENCE,
} from "../lib/agent-definitions.types";
import { fetchSettings, updateSettings } from "../lib/settings-api";
import type { SettingsUpdateRequest } from "../lib/settings.types";

interface SummarySettingsProps {
  onCloseSettings: () => void;
  isAgentSettingsLocked: boolean;
}

interface SummaryNumberFieldProps {
  label: string;
  hint: string;
  value: string;
  min?: number;
  onChange: (value: string) => void;
}

interface SummarySettingLabelProps {
  label: string;
  description: string;
}

interface SummaryPromptLinkProps {
  label: string;
  locationText: string;
  actionText: string;
  onClick: () => void;
}

interface SummaryFormValues {
  minChapterWordCount: number | null;
  batchSize: number | null;
  longTermInterval: number | null;
  chapterTargetLength: number | null;
  longTermTargetLength: number | null;
}

function parseInteger(value: string, minimum: number): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= minimum ? parsed : null;
}

function SummarySettingLabel({ label, description }: SummarySettingLabelProps) {
  return (
    <Flex
      direction="column"
      gap="1"
    >
      <Text
        size="2"
        weight="medium"
      >
        {label}
      </Text>
      <Text
        size="1"
        color="gray"
      >
        {description}
      </Text>
    </Flex>
  );
}

function SummaryNumberField({ label, hint, value, min = 1, onChange }: SummaryNumberFieldProps) {
  const { t } = useTranslation();

  return (
    <Flex
      align="center"
      justify="between"
      gap="4"
    >
      <SummarySettingLabel
        label={label}
        description={hint}
      />
      <StepperNumberInput
        value={value}
        min={min}
        width={160}
        increaseAriaLabel={t("settings.increaseValue")}
        decreaseAriaLabel={t("settings.decreaseValue")}
        onChange={onChange}
      />
    </Flex>
  );
}

function SummaryPromptLink({ label, locationText, actionText, onClick }: SummaryPromptLinkProps) {
  return (
    <Flex
      direction="column"
      gap="1"
    >
      <Text
        size="2"
        weight="medium"
      >
        {label}
      </Text>
      <Flex
        align="center"
        gap="1"
        wrap="wrap"
      >
        <Text
          size="1"
          color="gray"
        >
          {locationText}
        </Text>
        <button
          type="button"
          onClick={onClick}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            padding: 0,
            border: "none",
            background: "transparent",
            color: "var(--accent-11)",
            textDecoration: "underline",
            cursor: "pointer",
            font: "inherit",
          }}
        >
          <Text
            size="1"
            style={{ color: "inherit" }}
          >
            {actionText}
          </Text>
          <ExternalLink size={14} />
        </button>
      </Flex>
    </Flex>
  );
}

function isSummaryRangeInvalidationError(error: unknown): boolean {
  if (!axios.isAxiosError(error) || error.response?.status !== 409) return false;
  const detail = error.response.data?.detail;
  return (
    typeof detail === "object" &&
    detail !== null &&
    "code" in detail &&
    detail.code === "summary_range_invalidation_required"
  );
}

export function SummarySettings({ onCloseSettings, isAgentSettingsLocked }: SummarySettingsProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: settings, isLoading: isSettingsLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });
  const { options: llmModelOptions, isLoading: isModelsLoading } = useLlmModelOptions();
  const [summaryModel, setSummaryModel] = useState(settings?.summaryModel ?? "");
  const [autoGenerateChapter, setAutoGenerateChapter] = useState(
    settings?.summaryAutoGenerateChapter ?? false,
  );
  const [autoGenerateLongTerm, setAutoGenerateLongTerm] = useState(
    settings?.summaryAutoGenerateLongTerm ?? false,
  );
  const [minChapterWordCount, setMinChapterWordCount] = useState(
    String(settings?.summaryMinChapterWordCount ?? ""),
  );
  const [batchSize, setBatchSize] = useState(String(settings?.summaryBatchSize ?? ""));
  const [longTermInterval, setLongTermInterval] = useState(
    String(settings?.summaryLongTermInterval ?? ""),
  );
  const [chapterTargetLength, setChapterTargetLength] = useState(
    String(settings?.summaryChapterTargetLength ?? ""),
  );
  const [longTermTargetLength, setLongTermTargetLength] = useState(
    String(settings?.summaryLongTermTargetLength ?? ""),
  );
  const [pendingInvalidationPayload, setPendingInvalidationPayload] =
    useState<SettingsUpdateRequest | null>(null);
  const [invalidationDialogOpen, setInvalidationDialogOpen] = useState(false);

  useEffect(() => {
    if (!settings) return;
    setSummaryModel(settings.summaryModel);
    setAutoGenerateChapter(settings.summaryAutoGenerateChapter);
    setAutoGenerateLongTerm(settings.summaryAutoGenerateLongTerm);
    setMinChapterWordCount(String(settings.summaryMinChapterWordCount));
    setBatchSize(String(settings.summaryBatchSize));
    setLongTermInterval(String(settings.summaryLongTermInterval));
    setChapterTargetLength(String(settings.summaryChapterTargetLength));
    setLongTermTargetLength(String(settings.summaryLongTermTargetLength));
  }, [settings]);

  const modelOptions = useMemo<ModelIdSelectOption[]>(
    () => [
      {
        value: SYSTEM_DEFAULT_MODEL_REFERENCE,
        id: t("settings.agentsFollowSystemSetting"),
        name: t("settings.agentsSystemDefaultModel"),
        taskType: "llm",
      },
      {
        value: SYSTEM_LIGHT_MODEL_REFERENCE,
        id: t("settings.agentsFollowSystemSetting"),
        name: t("settings.agentsSystemLightModel"),
        taskType: "llm",
      },
      ...llmModelOptions,
    ],
    [llmModelOptions, t],
  );

  const formValues = useMemo<SummaryFormValues>(
    () => ({
      minChapterWordCount: parseInteger(minChapterWordCount, 0),
      batchSize: parseInteger(batchSize, 1),
      longTermInterval: parseInteger(longTermInterval, 1),
      chapterTargetLength: parseInteger(chapterTargetLength, 1),
      longTermTargetLength: parseInteger(longTermTargetLength, 1),
    }),
    [batchSize, chapterTargetLength, longTermInterval, longTermTargetLength, minChapterWordCount],
  );

  const isFormValid = Object.values(formValues).every((value) => value !== null);
  const hasChanges = Boolean(
    settings &&
    isFormValid &&
    (summaryModel !== settings.summaryModel ||
      autoGenerateChapter !== settings.summaryAutoGenerateChapter ||
      autoGenerateLongTerm !== settings.summaryAutoGenerateLongTerm ||
      formValues.minChapterWordCount !== settings.summaryMinChapterWordCount ||
      formValues.batchSize !== settings.summaryBatchSize ||
      formValues.longTermInterval !== settings.summaryLongTermInterval ||
      formValues.chapterTargetLength !== settings.summaryChapterTargetLength ||
      formValues.longTermTargetLength !== settings.summaryLongTermTargetLength),
  );

  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: (nextSettings) => {
      queryClient.setQueryData(["settings"], nextSettings);
      setPendingInvalidationPayload(null);
      setInvalidationDialogOpen(false);
      toast.success(t("settings.saved"));
    },
    onError: (error, payload) => {
      if (isSummaryRangeInvalidationError(error) && !payload.confirm_summary_range_invalidation) {
        setPendingInvalidationPayload(payload);
        setInvalidationDialogOpen(true);
        return;
      }
      toast.error(t("settings.saveFailed"));
    },
  });

  const buildPayload = useCallback((): SettingsUpdateRequest | null => {
    if (!settings || !isFormValid) {
      toast.error(t("settings.summaryInvalidNumber"));
      return null;
    }

    return {
      ...(summaryModel !== settings.summaryModel ? { summary_model: summaryModel } : {}),
      summary_auto_generate_chapter: autoGenerateChapter,
      summary_auto_generate_long_term: autoGenerateLongTerm,
      summary_min_chapter_word_count: formValues.minChapterWordCount ?? 0,
      summary_batch_size: formValues.batchSize ?? 1,
      summary_long_term_interval: formValues.longTermInterval ?? 1,
      summary_chapter_target_length: formValues.chapterTargetLength ?? 1,
      summary_long_term_target_length: formValues.longTermTargetLength ?? 1,
    };
  }, [
    autoGenerateChapter,
    autoGenerateLongTerm,
    formValues,
    isFormValid,
    settings,
    summaryModel,
    t,
  ]);

  const handleSave = useCallback(() => {
    const payload = buildPayload();
    if (payload) updateMutation.mutate(payload);
  }, [buildPayload, updateMutation]);

  const handleConfirmInvalidation = useCallback(() => {
    if (!pendingInvalidationPayload) return;
    updateMutation.mutate({
      ...pendingInvalidationPayload,
      confirm_summary_range_invalidation: true,
    });
  }, [pendingInvalidationPayload, updateMutation]);

  const handleGoToPromptChain = useCallback(
    (promptId: string) => {
      onCloseSettings();
      const params = new URLSearchParams({ prompt: promptId });
      navigate(`/prompt-chains?${params.toString()}`);
    },
    [navigate, onCloseSettings],
  );

  if (isSettingsLoading || isModelsLoading || !settings) {
    return (
      <Flex
        align="center"
        justify="center"
        style={{ height: "100%" }}
      >
        <Spinner size={18} />
      </Flex>
    );
  }

  return (
    <Box>
      <Flex
        direction="column"
        gap="5"
      >
        <Flex
          align="center"
          justify="between"
          gap="4"
        >
          <SummarySettingLabel
            label={t("settings.summaryModel")}
            description={t("settings.summaryModelHint")}
          />
          <ModelIdSelect
            value={summaryModel}
            onChange={(value) => setSummaryModel(value)}
            models={modelOptions}
            isLoading={isModelsLoading}
            editable={false}
            allowCustomValue={false}
            disabled={isAgentSettingsLocked || llmModelOptions.length === 0}
            triggerStyle={{ width: 160 }}
            triggerClassName="select-trigger--background"
            contentClassName="settings-background-panel"
          />
        </Flex>

        <Flex
          direction="column"
          gap="4"
        >
          <Flex
            align="center"
            justify="between"
            gap="4"
          >
            <SummarySettingLabel
              label={t("settings.summaryAutoGenerateChapter")}
              description={t("settings.summaryAutoGenerateChapterHint")}
            />
            <Switch
              checked={autoGenerateChapter}
              onCheckedChange={setAutoGenerateChapter}
            />
          </Flex>
          <Flex
            align="center"
            justify="between"
            gap="4"
          >
            <SummarySettingLabel
              label={t("settings.summaryAutoGenerateLongTerm")}
              description={t("settings.summaryAutoGenerateLongTermHint")}
            />
            <Switch
              checked={autoGenerateLongTerm}
              onCheckedChange={setAutoGenerateLongTerm}
            />
          </Flex>
        </Flex>

        <Flex
          direction="column"
          gap="4"
        >
          <SummaryNumberField
            label={t("settings.summaryMinChapterWordCount")}
            hint={t("settings.summaryMinChapterWordCountHint")}
            value={minChapterWordCount}
            min={0}
            onChange={setMinChapterWordCount}
          />
          <SummaryNumberField
            label={t("settings.summaryBatchSize")}
            hint={t("settings.summaryBatchSizeHint")}
            value={batchSize}
            onChange={setBatchSize}
          />
          <SummaryNumberField
            label={t("settings.summaryLongTermInterval")}
            hint={t("settings.summaryLongTermIntervalHint")}
            value={longTermInterval}
            onChange={setLongTermInterval}
          />
          <SummaryNumberField
            label={t("settings.summaryChapterTargetLength")}
            hint={t("settings.summaryChapterTargetLengthHint")}
            value={chapterTargetLength}
            onChange={setChapterTargetLength}
          />
          <SummaryNumberField
            label={t("settings.summaryLongTermTargetLength")}
            hint={t("settings.summaryLongTermTargetLengthHint")}
            value={longTermTargetLength}
            onChange={setLongTermTargetLength}
          />
        </Flex>

        <Flex
          direction="column"
          gap="4"
        >
          <SummaryPromptLink
            label={t("settings.summaryChapterPrompt")}
            locationText={t("settings.summaryPromptChainLocationPrefix", {
              prompt: t("settings.summaryChapterPromptName"),
            })}
            actionText={t("settings.summaryPromptChainAction")}
            onClick={() => handleGoToPromptChain("memory-chapter-summary")}
          />
          <SummaryPromptLink
            label={t("settings.summaryLongTermPrompt")}
            locationText={t("settings.summaryPromptChainLocationPrefix", {
              prompt: t("settings.summaryLongTermPromptName"),
            })}
            actionText={t("settings.summaryPromptChainAction")}
            onClick={() => handleGoToPromptChain("memory-range-summary")}
          />
        </Flex>

        <Button
          onClick={handleSave}
          disabled={!hasChanges || updateMutation.isPending}
          style={{ alignSelf: "flex-start" }}
        >
          {updateMutation.isPending ? t("common.loading") : t("common.save")}
        </Button>
      </Flex>

      <ConfirmDialog
        open={invalidationDialogOpen}
        onOpenChange={(open) => {
          setInvalidationDialogOpen(open);
          if (!open) setPendingInvalidationPayload(null);
        }}
        onConfirm={handleConfirmInvalidation}
        title={t("settings.summaryRangeInvalidationTitle")}
        description={t("settings.summaryRangeInvalidationDescription")}
        confirmText={t("settings.summaryRangeInvalidationConfirm")}
        cancelText={t("common.cancel")}
        confirmColor="red"
        loading={updateMutation.isPending}
      />
    </Box>
  );
}
