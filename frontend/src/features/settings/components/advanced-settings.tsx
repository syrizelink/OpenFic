import { Box, Button, Flex, Switch, Text, Tooltip } from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Info } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog, Spinner, toast } from "@/components";

import {
  clearAuditDetails,
  fetchAuditDetailsStorage,
  fetchSettings,
  updateSettings,
} from "../lib/settings-api";
import type { Settings, SettingsUpdateRequest } from "../lib/settings.types";

function formatBytes(bytes: number, locale: string): string {
  if (bytes < 1024) return `${bytes} B`;
  const unit = bytes < 1024 * 1024 ? "KB" : "MB";
  const divisor = unit === "KB" ? 1024 : 1024 * 1024;
  return (
    new Intl.NumberFormat(locale, {
      maximumFractionDigits: 1,
    }).format(bytes / divisor) + ` ${unit}`
  );
}

export function AdvancedSettings() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [isClearDialogOpen, setIsClearDialogOpen] = useState(false);
  const { data: settings, isLoading: isSettingsLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });
  const { data: storage, isLoading: isStorageLoading } = useQuery({
    queryKey: ["audit-details-storage"],
    queryFn: fetchAuditDetailsStorage,
  });
  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onMutate: async (patch: SettingsUpdateRequest) => {
      await queryClient.cancelQueries({ queryKey: ["settings"] });
      const previousSettings = queryClient.getQueryData<Settings>(["settings"]);

      if (previousSettings && patch.audit_persist_details !== undefined) {
        queryClient.setQueryData<Settings>(["settings"], {
          ...previousSettings,
          auditPersistDetails: patch.audit_persist_details,
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
  const clearMutation = useMutation({
    mutationFn: clearAuditDetails,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["audit-details-storage"] });
      setIsClearDialogOpen(false);
      toast.success(t("settings.advancedClearSuccess"));
    },
    onError: () => toast.error(t("settings.advancedClearFailed")),
  });

  if (isSettingsLoading || isStorageLoading || !settings || !storage) {
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
                {t("settings.advancedPersistDetails")}
              </Text>
              <Tooltip
                content={
                  <Flex
                    direction="column"
                    gap="1"
                  >
                    <Text size="1">{t("settings.advancedPersistDetailsTooltipRecords")}</Text>
                    <Text size="1">{t("settings.advancedPersistDetailsTooltipStorage")}</Text>
                    <Text size="1">
                      {t("settings.advancedPersistDetailsTooltipRecommendation")}
                    </Text>
                  </Flex>
                }
              >
                <button
                  type="button"
                  className="advanced-settings-info-button"
                  aria-label={t("settings.advancedPersistDetailsTooltipLabel")}
                >
                  <Info size={14} />
                </button>
              </Tooltip>
            </Flex>
            <Text
              size="1"
              color="gray"
            >
              {t("settings.advancedPersistDetailsHint")}
            </Text>
          </Flex>
          <Switch
            checked={settings.auditPersistDetails}
            aria-label={t("settings.advancedPersistDetails")}
            onCheckedChange={(checked) => {
              updateMutation.mutate({ audit_persist_details: checked });
            }}
          />
        </Flex>

        <Flex
          align="end"
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
              {t("settings.advancedStorage")}
            </Text>
            <Text
              size="1"
              color="gray"
            >
              {t("settings.advancedStorageValue", {
                size: formatBytes(storage.detailBytes, i18n.language),
                count: storage.detailRecordsCount,
              })}
            </Text>
          </Flex>
          <Button
            color="red"
            variant="soft"
            disabled={storage.detailRecordsCount === 0 || clearMutation.isPending}
            onClick={() => setIsClearDialogOpen(true)}
          >
            {t("settings.advancedClear")}
          </Button>
        </Flex>
      </Flex>

      <ConfirmDialog
        open={isClearDialogOpen}
        onOpenChange={setIsClearDialogOpen}
        onConfirm={() => clearMutation.mutate()}
        title={t("settings.advancedClearTitle")}
        description={t("settings.advancedClearDescription")}
        confirmText={t("settings.advancedClear")}
        confirmColor="red"
        loading={clearMutation.isPending}
      />
    </Box>
  );
}
