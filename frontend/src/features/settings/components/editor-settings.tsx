import { Box, Flex, Switch, Text, Tooltip } from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Info } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Spinner, toast } from "@/components";

import { fetchSettings, updateSettings } from "../lib/settings-api";
import type { Settings, SettingsUpdateRequest } from "../lib/settings.types";

export function EditorSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });
  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onMutate: async (patch: SettingsUpdateRequest) => {
      await queryClient.cancelQueries({ queryKey: ["settings"] });
      const previousSettings = queryClient.getQueryData<Settings>(["settings"]);

      if (previousSettings && patch.editor_auto_indent !== undefined) {
        queryClient.setQueryData<Settings>(["settings"], {
          ...previousSettings,
          editorAutoIndent: patch.editor_auto_indent,
        });
      }

      if (previousSettings && patch.editor_auto_convert_punctuation !== undefined) {
        queryClient.setQueryData<Settings>(["settings"], {
          ...previousSettings,
          editorAutoConvertPunctuation: patch.editor_auto_convert_punctuation,
        });
      }

      if (previousSettings && patch.editor_auto_pair_symbols !== undefined) {
        queryClient.setQueryData<Settings>(["settings"], {
          ...previousSettings,
          editorAutoPairSymbols: patch.editor_auto_pair_symbols,
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

  if (isLoading || !settings) {
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
          <Flex
            direction="column"
            gap="1"
          >
            <Flex
              align="center"
              gap="1"
            >
              <Text
                size="2"
                weight="medium"
              >
                {t("settings.editorAutoIndent")}
              </Text>
              <Tooltip content={t("settings.editorAutoIndentTooltip")}>
                <button
                  type="button"
                  className="advanced-settings-info-button"
                  aria-label={t("settings.editorAutoIndentTooltipLabel")}
                >
                  <Info size={14} />
                </button>
              </Tooltip>
            </Flex>
            <Text
              size="1"
              color="gray"
            >
              {t("settings.editorAutoIndentHint")}
            </Text>
          </Flex>
          <Switch
            checked={settings.editorAutoIndent}
            aria-label={t("settings.editorAutoIndent")}
            onCheckedChange={(checked) => {
              updateMutation.mutate({ editor_auto_indent: checked });
            }}
          />
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
            <Flex
              align="center"
              gap="1"
            >
              <Text
                size="2"
                weight="medium"
              >
                {t("settings.editorAutoConvertPunctuation")}
              </Text>
              <Tooltip content={t("settings.editorAutoConvertPunctuationTooltipSymbols")}>
                <button
                  type="button"
                  className="advanced-settings-info-button"
                  aria-label={t("settings.editorAutoConvertPunctuationTooltipLabel")}
                >
                  <Info size={14} />
                </button>
              </Tooltip>
            </Flex>
            <Text
              size="1"
              color="gray"
            >
              {t("settings.editorAutoConvertPunctuationHint")}
            </Text>
          </Flex>
          <Switch
            checked={settings.editorAutoConvertPunctuation}
            aria-label={t("settings.editorAutoConvertPunctuation")}
            onCheckedChange={(checked) => {
              updateMutation.mutate({ editor_auto_convert_punctuation: checked });
            }}
          />
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
            <Flex
              align="center"
              gap="1"
            >
              <Text
                size="2"
                weight="medium"
              >
                {t("settings.editorAutoPairSymbols")}
              </Text>
              <Tooltip content={t("settings.editorAutoPairSymbolsTooltipSymbols")}>
                <button
                  type="button"
                  className="advanced-settings-info-button"
                  aria-label={t("settings.editorAutoPairSymbolsTooltipLabel")}
                >
                  <Info size={14} />
                </button>
              </Tooltip>
            </Flex>
            <Text
              size="1"
              color="gray"
            >
              {t("settings.editorAutoPairSymbolsHint")}
            </Text>
          </Flex>
          <Switch
            checked={settings.editorAutoPairSymbols}
            aria-label={t("settings.editorAutoPairSymbols")}
            onCheckedChange={(checked) => {
              updateMutation.mutate({ editor_auto_pair_symbols: checked });
            }}
          />
        </Flex>
      </Flex>
    </Box>
  );
}
