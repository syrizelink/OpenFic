/**
 * Advanced Params Section Component
 *
 * 模型高级参数面板，包含温度、Top-P、Top-K 等参数。
 */

import { useState, useEffect } from "react";
import { Box, Button, Flex, Grid, Text } from "@radix-ui/themes";
import { ChevronDown, ChevronLeft } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { useTranslation } from "react-i18next";
import type { Control, FieldValues, Path, UseFormGetValues, UseFormSetValue } from "react-hook-form";
import { Controller, useWatch } from "react-hook-form";

import { LabeledSelect } from "@/components/select";
import { SliderField } from "@/components/slider-field";

interface AdvancedParamsSectionProps<T extends FieldValues> {
  control: Control<T>;
  getValues: UseFormGetValues<T>;
  setValue: UseFormSetValue<T>;
  modelId?: string;
  isDeepSeekProvider?: boolean;
}

// 参数配置
const PARAM_CONFIGS = [
  { name: "temperature", labelKey: "temperature", descKey: "temperatureDesc", defaultValue: 1, min: 0, max: 2, sliderStep: 0.01, inputStep: 0.01 },
  { name: "topP", labelKey: "topP", descKey: "topPDesc", defaultValue: 1, min: 0, max: 1, sliderStep: 0.01, inputStep: 0.01 },
  { name: "topK", labelKey: "topK", descKey: "topKDesc", defaultValue: 0, min: 0, max: 1000, sliderStep: 1, inputStep: 1 },
  { name: "minP", labelKey: "minP", descKey: "minPDesc", defaultValue: 0, min: 0, max: 1, sliderStep: 0.01, inputStep: 0.01 },
  { name: "topA", labelKey: "topA", descKey: "topADesc", defaultValue: 0, min: 0, max: 1, sliderStep: 0.01, inputStep: 0.01 },
  { name: "frequencyPenalty", labelKey: "frequencyPenalty", descKey: "frequencyPenaltyDesc", defaultValue: 0, min: -2, max: 2, sliderStep: 0.01, inputStep: 0.01 },
  { name: "presencePenalty", labelKey: "presencePenalty", descKey: "presencePenaltyDesc", defaultValue: 0, min: -2, max: 2, sliderStep: 0.01, inputStep: 0.01 },
  { name: "repetitionPenalty", labelKey: "repetitionPenalty", descKey: "repetitionPenaltyDesc", defaultValue: 1, min: 0, max: 2, sliderStep: 0.01, inputStep: 0.01 },
  { name: "maxTokens", labelKey: "maxTokens", descKey: "maxTokensDesc", defaultValue: 0, min: -1, max: 2000000, sliderStep: 100, inputStep: 1 },
  { name: "contextLength", labelKey: "contextLength", descKey: "contextLengthDesc", defaultValue: 128000, min: 1, max: 2000000, sliderStep: 1000, inputStep: 1 },
] as const;

export function AdvancedParamsSection<T extends FieldValues>({
  control,
  getValues,
  setValue,
  modelId,
  isDeepSeekProvider = false,
}: AdvancedParamsSectionProps<T>) {
  const { t } = useTranslation();
  const [showAdvanced, setShowAdvanced] = useState(false);
  const deepseekThinkingType = useWatch({
    control,
    name: "deepseekThinkingType" as Path<T>,
  });

  // 当打开高级参数面板时，初始化null值为默认值
  useEffect(() => {
    if (showAdvanced) {
      const currentValues = getValues();

      for (const config of PARAM_CONFIGS) {
        const fieldName = config.name as keyof T;
        const fieldValue = currentValues[fieldName];
        if (fieldValue === null || fieldValue === undefined) {
          // @ts-expect-error FieldValues泛型类型断言
          setValue(fieldName, config.defaultValue);
        }
      }
    }
  }, [showAdvanced, setValue, getValues]);


  return (
    <>
      {/* 展开/折叠按钮 */}
      <Button
        type="button"
        variant="soft"
        onClick={() => setShowAdvanced(!showAdvanced)}
        style={{ justifyContent: "flex-start" }}
      >
        <Flex align="center" justify="between" style={{ width: "100%" }}>
          <Text>{t("models.advancedParams")}</Text>
          <AnimatePresence mode="wait">
            <motion.div
              key={showAdvanced ? "down" : "left"}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              {showAdvanced ? <ChevronDown size={16} /> : <ChevronLeft size={16} />}
            </motion.div>
          </AnimatePresence>
        </Flex>
      </Button>

      {/* 参数面板 */}
      <AnimatePresence>
        {showAdvanced && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            style={{ overflow: "hidden" }}
          >
            <Box style={{ paddingTop: "var(--space-4)" }}>
              <Grid columns="2" gap="4" style={{ paddingLeft: 4, paddingRight: 4 }}>
                {PARAM_CONFIGS.map((config) => (
                  <SliderField
                    key={config.name}
                    name={config.name as Path<T>}
                    label={t(`models.${config.labelKey}`)}
                    description={t(`models.${config.descKey}`)}
                    control={control}
                    defaultValue={config.defaultValue}
                    min={config.min}
                    max={config.max}
                    sliderStep={config.sliderStep}
                    inputStep={config.inputStep}
                    inputKey={`${config.name}-${modelId || "new"}`}
                  />
                ))}
              </Grid>

              {isDeepSeekProvider && (
                <Grid columns="2" gap="4" mt="4" style={{ paddingLeft: 4, paddingRight: 4 }}>
                  <Flex direction="column" gap="2">
                    <Text size="2" weight="medium" color="gray">
                      {t("models.deepseekThinkingType")}
                    </Text>
                    <Controller
                      name={"deepseekThinkingType" as Path<T>}
                      control={control}
                      render={({ field }) => (
                        <LabeledSelect
                          value={String(field.value || "enabled")}
                          options={[
                            { value: "enabled", label: "enabled" },
                            { value: "disabled", label: "disabled" },
                          ]}
                          onChange={field.onChange}
                          triggerStyle={{ width: "100%" }}
                        />
                      )}
                    />
                    <Text size="1" color="gray">
                      {t("models.deepseekThinkingTypeDesc")}
                    </Text>
                  </Flex>

                  {deepseekThinkingType === "enabled" && (
                    <Flex direction="column" gap="2">
                      <Text size="2" weight="medium" color="gray">
                        {t("models.deepseekReasoningEffort")}
                      </Text>
                      <Controller
                        name={"deepseekReasoningEffort" as Path<T>}
                        control={control}
                        render={({ field }) => (
                          <LabeledSelect
                            value={String(field.value || "high")}
                            options={[
                              { value: "high", label: "high" },
                              { value: "max", label: "max" },
                            ]}
                            onChange={field.onChange}
                            triggerStyle={{ width: "100%" }}
                          />
                        )}
                      />
                      <Text size="1" color="gray">
                        {t("models.deepseekReasoningEffortDesc")}
                      </Text>
                    </Flex>
                  )}
                </Grid>
              )}
            </Box>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
