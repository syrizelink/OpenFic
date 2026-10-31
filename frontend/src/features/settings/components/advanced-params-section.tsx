/**
 * Advanced Params Section Component
 *
 * 模型高级参数面板，包含温度、Top-P、Top-K 等参数。
 */

import { Box, Button, Flex, Grid, Text, TextField } from "@radix-ui/themes";
import { ChevronDown, ChevronLeft, Info } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { useState } from "react";
import { Controller, type Control, type FieldValues, type Path } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { InfoTooltip } from "@/components";
import { SliderField } from "@/components/slider-field";

interface AdvancedParamsSectionProps<T extends FieldValues> {
  control: Control<T>;
  modelId?: string;
}

// 参数配置
const PARAM_CONFIGS = [
  {
    name: "temperature",
    labelKey: "temperature",
    descKey: "temperatureDesc",
    defaultValue: 1,
    min: 0,
    max: 2,
    sliderStep: 0.01,
    inputStep: 0.01,
  },
  {
    name: "topP",
    labelKey: "topP",
    descKey: "topPDesc",
    defaultValue: 1,
    min: 0,
    max: 1,
    sliderStep: 0.01,
    inputStep: 0.01,
  },
  {
    name: "topK",
    labelKey: "topK",
    descKey: "topKDesc",
    defaultValue: 0,
    min: 0,
    max: 128,
    sliderStep: 1,
    inputStep: 1,
  },
  {
    name: "minP",
    labelKey: "minP",
    descKey: "minPDesc",
    defaultValue: 0,
    min: 0,
    max: 1,
    sliderStep: 0.01,
    inputStep: 0.01,
  },
  {
    name: "topA",
    labelKey: "topA",
    descKey: "topADesc",
    defaultValue: 0,
    min: 0,
    max: 1,
    sliderStep: 0.01,
    inputStep: 0.01,
  },
  {
    name: "frequencyPenalty",
    labelKey: "frequencyPenalty",
    descKey: "frequencyPenaltyDesc",
    defaultValue: 0,
    min: -2,
    max: 2,
    sliderStep: 0.01,
    inputStep: 0.01,
  },
  {
    name: "presencePenalty",
    labelKey: "presencePenalty",
    descKey: "presencePenaltyDesc",
    defaultValue: 0,
    min: -2,
    max: 2,
    sliderStep: 0.01,
    inputStep: 0.01,
  },
  {
    name: "repetitionPenalty",
    labelKey: "repetitionPenalty",
    descKey: "repetitionPenaltyDesc",
    defaultValue: 1,
    min: 0,
    max: 2,
    sliderStep: 0.01,
    inputStep: 0.01,
  },
] as const;

// 空值表示不传 max_tokens，由后端按模型默认输出上限处理，因此不能用带默认值的滑块
function MaxTokensField<T extends FieldValues>({
  control,
  inputId,
}: {
  control: Control<T>;
  inputId: string;
}) {
  const { t } = useTranslation();

  return (
    <Flex
      direction="column"
      gap="2"
    >
      <Flex
        justify="between"
        align="center"
        gap="2"
      >
        <Text
          as="label"
          htmlFor={inputId}
          size="2"
          weight="medium"
          color="gray"
        >
          {t("models.maxTokens")}
        </Text>
        <Controller
          name={"maxTokens" as Path<T>}
          control={control}
          render={({ field }) => (
            <TextField.Root
              id={inputId}
              type="number"
              min={1}
              step={1}
              value={field.value ?? ""}
              placeholder={t("models.maxTokensPlaceholder")}
              onChange={(event) => {
                const value = event.target.value;
                field.onChange(value === "" ? null : Number(value));
              }}
              onBlur={(event) => {
                const value = Number(event.currentTarget.value);
                const normalizedValue = Number.isFinite(value) && value >= 1 ? Math.round(value) : null;
                if (normalizedValue !== field.value) {
                  field.onChange(normalizedValue);
                }
                field.onBlur();
              }}
              style={{ width: 120 }}
            />
          )}
        />
      </Flex>
      <Text
        size="1"
        color="gray"
      >
        {t("models.maxTokensDesc")}
      </Text>
    </Flex>
  );
}

export function AdvancedParamsSection<T extends FieldValues>({
  control,
  modelId,
}: AdvancedParamsSectionProps<T>) {
  const { t } = useTranslation();
  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <>
      {/* 展开/折叠按钮 */}
      <Button
        type="button"
        variant="soft"
        color="gray"
        highContrast
        onClick={() => setShowAdvanced(!showAdvanced)}
        style={{ justifyContent: "flex-start" }}
      >
        <Flex
          align="center"
          justify="between"
          style={{ width: "100%" }}
        >
          <Flex
            align="center"
            gap="1"
          >
            <Text>{t("models.advancedParams")}</Text>
            <InfoTooltip
              content={
                <Flex
                  direction="column"
                  gap="1"
                >
                  <Text size="1">{t("models.advancedParamsTooltipGeneration")}</Text>
                  <Text size="1">{t("models.advancedParamsTooltipUnsupported")}</Text>
                  <Text size="1">{t("models.advancedParamsTooltipRecommendation")}</Text>
                </Flex>
              }
            >
              <span
                className="advanced-params-info-button"
                aria-label={t("models.advancedParamsTooltipLabel")}
                role="img"
              >
                <Info size={14} />
              </span>
            </InfoTooltip>
          </Flex>
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
              <Grid
                columns="2"
                gap="4"
                style={{ paddingLeft: 4, paddingRight: 4 }}
              >
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
                <MaxTokensField
                  control={control}
                  inputId={`max-tokens-${modelId || "new"}`}
                />
              </Grid>
            </Box>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
