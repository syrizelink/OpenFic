import { Box, Button, Flex, Switch, Text } from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
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
import type { Settings, SettingsUpdateRequest } from "../lib/settings.types";

import "./context-settings.css";

const numericFields = [
  [
    "compaction_trigger_ratio",
    "compactionTriggerRatio",
    "contextTriggerRatio",
    "contextTriggerRatioHint",
    true,
  ],
  [
    "compaction_tail_token_budget",
    "compactionTailTokenBudget",
    "contextTailTokenBudget",
    "contextTailTokenBudgetHint",
    false,
  ],
  [
    "compaction_tail_window_ratio",
    "compactionTailWindowRatio",
    "contextTailWindowRatio",
    "contextTailWindowRatioHint",
    true,
  ],
  [
    "compaction_min_compactable_tokens",
    "compactionMinCompactableTokens",
    "contextMinCompactableTokens",
    "contextMinCompactableTokensHint",
    false,
  ],
  [
    "prune_protected_tokens",
    "pruneProtectedTokens",
    "contextPruneBudget",
    "contextPruneBudgetHint",
    false,
  ],
  [
    "prune_minimum_tokens",
    "pruneMinimumTokens",
    "contextPruneOverflow",
    "contextPruneOverflowHint",
    false,
  ],
] as const;

type NumericKey = (typeof numericFields)[number][0];
type NumericField = (typeof numericFields)[number];

export function ContextSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { options: llmModelOptions, isLoading: isModelsLoading } = useLlmModelOptions();
  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });
  const [values, setValues] = useState<Record<NumericKey, string>>({
    compaction_trigger_ratio: "",
    compaction_tail_token_budget: "",
    compaction_tail_window_ratio: "",
    compaction_min_compactable_tokens: "",
    prune_protected_tokens: "",
    prune_minimum_tokens: "",
  });
  const lastSavedNumbers = useRef("");

  useEffect(() => {
    if (!settings) return;
    const savedNumbers = numericFields.map(([, property]) => settings[property]).join("|");
    if (lastSavedNumbers.current === savedNumbers) return;
    lastSavedNumbers.current = savedNumbers;
    setValues(
      Object.fromEntries(
        numericFields.map(([key, property, , , ratio]) => [
          key,
          String(ratio ? Number((settings[property] * 100).toPrecision(15)) : settings[property]),
        ]),
      ) as Record<NumericKey, string>,
    );
  }, [settings]);

  const parsed = Object.fromEntries(
    numericFields.map(([key, , , , ratio]) => {
      const value = Number(values[key]);
      return [
        key,
        values[key].trim() !== "" &&
        Number.isFinite(value) &&
        value > 0 &&
        (ratio ? value <= 100 : Number.isInteger(value))
          ? ratio
            ? value / 100
            : value
          : null,
      ];
    }),
  ) as Record<NumericKey, number | null>;
  const changedNumbers = settings
    ? numericFields.filter(([key, property, , , ratio]) => {
        const nextValue = parsed[key];
        return (
          nextValue !== null &&
          (ratio
            ? Math.abs(nextValue - settings[property]) > 1e-12
            : nextValue !== settings[property])
        );
      })
    : [];
  const isValid = numericFields.every(([key]) => parsed[key] !== null);
  const modelOptions: ModelIdSelectOption[] = [
    {
      value: "__session_model__",
      id: t("settings.agentsFollowSystemSetting"),
      name: t("settings.contextSessionModel"),
      taskType: "llm",
    },
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
  ];
  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onMutate: async (patch: SettingsUpdateRequest) => {
      await queryClient.cancelQueries({ queryKey: ["settings"] });
      const previousSettings = queryClient.getQueryData<Settings>(["settings"]);

      if (previousSettings) {
        queryClient.setQueryData<Settings>(["settings"], {
          ...previousSettings,
          compressSystemPrompts:
            patch.compress_system_prompts ?? previousSettings.compressSystemPrompts,
          autoCompactContext: patch.auto_compact_context ?? previousSettings.autoCompactContext,
          autoPruneToolOutputs:
            patch.auto_prune_tool_outputs ?? previousSettings.autoPruneToolOutputs,
        });
      }

      return { previousSettings };
    },
    onSuccess: (nextSettings) => {
      queryClient.setQueryData(["settings"], nextSettings);
      toast.success(t("settings.saved"));
    },
    onError: (_error, _patch, context) => {
      if (context?.previousSettings) {
        queryClient.setQueryData(["settings"], context.previousSettings);
      }
      toast.error(t("settings.saveFailed"));
    },
  });

  if (isLoading || isModelsLoading || !settings) {
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

  const renderNumericField = ([key, , label, hint, ratio]: NumericField) => (
    <Flex
      key={key}
      className="context-settings__row"
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
          {t(`settings.${label}`)}
        </Text>
        <Text
          size="1"
          color="gray"
        >
          {t(`settings.${hint}`)}
        </Text>
      </Flex>
      <StepperNumberInput
        value={values[key]}
        min={0}
        max={ratio ? 100 : undefined}
        step={1}
        unit={ratio ? "%" : "tokens"}
        width={160}
        increaseAriaLabel={t("settings.increaseValue")}
        decreaseAriaLabel={t("settings.decreaseValue")}
        onChange={(value) => setValues((current) => ({ ...current, [key]: value }))}
      />
    </Flex>
  );

  return (
    <Box>
      <Flex
        direction="column"
        gap="5"
      >
        <Flex
          className="context-settings__row"
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
              {t("settings.contextCompressSystemPrompts")}
            </Text>
            <Text
              size="1"
              color="gray"
            >
              {t("settings.contextCompressSystemPromptsHint")}
            </Text>
          </Flex>
          <Switch
            checked={settings.compressSystemPrompts}
            aria-label={t("settings.contextCompressSystemPrompts")}
            onCheckedChange={(checked) =>
              updateMutation.mutate({ compress_system_prompts: checked })
            }
          />
        </Flex>
        <Flex
          className="context-settings__row"
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
              {t("settings.contextAutoCompact")}
            </Text>
            <Text
              size="1"
              color="gray"
            >
              {t("settings.contextAutoCompactHint")}
            </Text>
          </Flex>
          <Switch
            checked={settings.autoCompactContext}
            aria-label={t("settings.contextAutoCompact")}
            onCheckedChange={(checked) => updateMutation.mutate({ auto_compact_context: checked })}
          />
        </Flex>
        <Flex
          className="context-settings__row"
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
              {t("settings.contextCompactionModel")}
            </Text>
            <Text
              size="1"
              color="gray"
            >
              {t("settings.contextCompactionModelHint")}
            </Text>
          </Flex>
          <Box className="context-settings__control">
            <ModelIdSelect
              value={settings.compactionModel}
              onChange={(value) => updateMutation.mutate({ compaction_model: value })}
              models={modelOptions}
              isLoading={isModelsLoading}
              editable={false}
              allowCustomValue={false}
              triggerClassName="select-trigger--background"
              contentClassName="settings-background-panel"
            />
          </Box>
        </Flex>
        {numericFields.slice(0, 4).map(renderNumericField)}
        <Flex
          className="context-settings__row"
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
              {t("settings.contextAutoPrune")}
            </Text>
            <Text
              size="1"
              color="gray"
            >
              {t("settings.contextAutoPruneHint")}
            </Text>
          </Flex>
          <Switch
            checked={settings.autoPruneToolOutputs}
            aria-label={t("settings.contextAutoPrune")}
            onCheckedChange={(checked) =>
              updateMutation.mutate({ auto_prune_tool_outputs: checked })
            }
          />
        </Flex>
        {numericFields.slice(4).map(renderNumericField)}
        <Flex justify="start">
          <Button
            disabled={changedNumbers.length === 0 || !isValid || updateMutation.isPending}
            onClick={() => {
              updateMutation.mutate(
                Object.fromEntries(
                  changedNumbers.map(([key]) => [key, parsed[key]]),
                ) as SettingsUpdateRequest,
              );
            }}
          >
            {t("common.save")}
          </Button>
        </Flex>
      </Flex>
    </Box>
  );
}
