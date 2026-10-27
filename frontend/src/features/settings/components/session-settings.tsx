import { Box, Button, Flex, Text } from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner, StepperNumberInput, toast } from "@/components";

import { fetchSettings, updateSettings } from "../lib/settings-api";

const fields = [
  ["llm_connect_timeout", "llmConnectTimeout", "sessionConnectTimeout"],
  ["llm_chunk_timeout", "llmChunkTimeout", "sessionChunkTimeout"],
  ["llm_request_timeout", "llmRequestTimeout", "sessionRequestTimeout"],
] as const;
type Key = (typeof fields)[number][0];

export function SessionSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: fetchSettings });
  const [values, setValues] = useState<Record<Key, string>>({
    llm_connect_timeout: "",
    llm_chunk_timeout: "",
    llm_request_timeout: "",
  });
  useEffect(() => {
    if (settings)
      setValues(
        Object.fromEntries(
          fields.map(([key, property]) => [key, String(settings[property])]),
        ) as Record<Key, string>,
      );
  }, [settings]);
  const mutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["settings"], data);
      toast.success(t("settings.saved"));
    },
    onError: () => toast.error(t("settings.saveFailed")),
  });
  if (!settings) return <Spinner size={18} />;
  const valid = fields.every(
    ([key]) =>
      values[key].trim() !== "" &&
      Number.isFinite(Number(values[key])) &&
      Number(values[key]) >= 1 &&
      Number(values[key]) <= 86400,
  );
  const changed = fields.some(([key, property]) => Number(values[key]) !== settings[property]);
  return (
    <Box>
      <Flex
        direction="column"
        gap="5"
      >
        <Text
          size="1"
          color="gray"
        >
          {t("settings.sessionTimeoutIntro")}
        </Text>
        {fields.map(([key, , label]) => (
          <Flex
            key={key}
            align="end"
            justify="between"
            gap="4"
            wrap="wrap"
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
                {t(`settings.${label}Hint`)}
              </Text>
            </Flex>
            <StepperNumberInput
              value={values[key]}
              min={1}
              max={86400}
              step={0.1}
              unit={t("settings.sessionTimeoutSeconds")}
              width={148}
              increaseAriaLabel={t("settings.increaseValue")}
              decreaseAriaLabel={t("settings.decreaseValue")}
              onChange={(value) => setValues((current) => ({ ...current, [key]: value }))}
            />
          </Flex>
        ))}
        <Flex justify="end">
          <Button
            disabled={!valid || !changed || mutation.isPending}
            onClick={() =>
              mutation.mutate(Object.fromEntries(fields.map(([key]) => [key, Number(values[key])])))
            }
          >
            {t("settings.save")}
          </Button>
        </Flex>
      </Flex>
    </Box>
  );
}
