import { Box, Button, Flex, Grid, Text, TextField, Tooltip } from "@radix-ui/themes";
import { ChevronDown, ChevronLeft, Info } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import type { Control, FieldValues, Path } from "react-hook-form";
import { Controller } from "react-hook-form";
import { useTranslation } from "react-i18next";

interface ModelMetadataSectionProps<T extends FieldValues> {
  control: Control<T>;
  modelId?: string;
  disabled?: boolean;
}

const PRICE_FIELDS = [
  { name: "inputPrice", labelKey: "inputPrice", descKey: "inputPriceDesc" },
  { name: "outputPrice", labelKey: "outputPrice", descKey: "outputPriceDesc" },
  { name: "cacheReadPrice", labelKey: "cacheReadPrice", descKey: "cacheReadPriceDesc" },
  { name: "cacheWritePrice", labelKey: "cacheWritePrice", descKey: "cacheWritePriceDesc" },
] as const;

function MetadataNumberField<T extends FieldValues>({
  control,
  name,
  label,
  description,
  inputId,
  min = 0,
  max,
  step = "any",
  disabled = false,
}: {
  control: Control<T>;
  name: Path<T>;
  label: string;
  description: string;
  inputId: string;
  min?: number;
  max?: number;
  step?: number | "any";
  disabled?: boolean;
}) {
  return (
    <Flex
      direction="column"
      gap="2"
    >
      <Text
        as="label"
        htmlFor={inputId}
        size="2"
        weight="medium"
        color="gray"
      >
        {label}
      </Text>
      <Controller
        name={name}
        control={control}
        render={({ field }) => (
          <TextField.Root
            id={inputId}
            type="number"
            min={min}
            max={max}
            step={step}
            value={field.value ?? 0}
            disabled={disabled}
            onChange={(event) => {
              const value = event.target.value;
              field.onChange(value === "" ? 0 : Number(value));
            }}
          />
        )}
      />
      <Text
        size="1"
        color="gray"
      >
        {description}
      </Text>
    </Flex>
  );
}

export function ModelMetadataSection<T extends FieldValues>({
  control,
  modelId,
  disabled = false,
}: ModelMetadataSectionProps<T>) {
  const { t } = useTranslation();
  const [showMetadata, setShowMetadata] = useState(false);
  const sectionId = `model-metadata-${modelId || "new"}`;

  return (
    <>
      <Button
        type="button"
        variant="soft"
        className="model-metadata-section-toggle"
        aria-expanded={showMetadata}
        aria-controls={sectionId}
        onClick={() => setShowMetadata((current) => !current)}
      >
        <Flex
          align="center"
          justify="between"
          className="model-metadata-section-header"
        >
          <Flex
            align="center"
            gap="1"
          >
            <Text>{t("models.metadata")}</Text>
            <Tooltip
              content={
                <Flex
                  direction="column"
                  gap="1"
                >
                  <Text size="1">{t("models.metadataTooltipContext")}</Text>
                  <Text size="1">{t("models.metadataTooltipPricing")}</Text>
                </Flex>
              }
            >
              <span
                className="advanced-params-info-button"
                aria-label={t("models.metadataTooltipLabel")}
                role="img"
              >
                <Info size={14} />
              </span>
            </Tooltip>
          </Flex>
          <AnimatePresence mode="wait">
            <motion.div
              key={showMetadata ? "down" : "left"}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              {showMetadata ? <ChevronDown size={16} /> : <ChevronLeft size={16} />}
            </motion.div>
          </AnimatePresence>
        </Flex>
      </Button>

      <AnimatePresence>
        {showMetadata && (
          <motion.div
            id={sectionId}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="model-metadata-section-panel"
          >
            <Box className="model-metadata-section-content">
              <Grid
                columns={{ initial: "1", sm: "2" }}
                gap="4"
                className="model-metadata-section-grid"
              >
                <MetadataNumberField
                  control={control}
                  name={"contextLength" as Path<T>}
                  label={t("models.contextLength")}
                  description={t("models.contextLengthDesc")}
                  inputId={`context-length-${modelId || "new"}`}
                  disabled={disabled}
                  min={0}
                  max={2000000}
                  step={1}
                />
                {PRICE_FIELDS.map((field) => (
                  <MetadataNumberField
                    key={field.name}
                    control={control}
                    name={field.name as Path<T>}
                    label={t(`models.${field.labelKey}`)}
                    description={t(`models.${field.descKey}`)}
                    inputId={`${field.name}-${modelId || "new"}`}
                    disabled={disabled}
                  />
                ))}
              </Grid>
            </Box>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
