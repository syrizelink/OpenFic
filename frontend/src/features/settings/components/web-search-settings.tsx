import { Box, Button, Flex, Switch, Text, TextField } from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner, toast } from "@/components";
import { LabeledSelect } from "@/components/select";

import {
  fetchWebSearchProviders,
  fetchWebSearchSettings,
  updateWebSearchSettings,
} from "../lib/web-search-api";
import type { WebSearchProviderField, WebSearchSettingsUpdateRequest } from "../lib/web-search-api";

const FIELD_LABEL_KEY_MAP: Record<string, string> = {
  bing_mkt: "settings.webSearchFieldBingMkt",
  ddgs_region: "settings.webSearchFieldDdgsRegion",
  searxng_base_url: "settings.webSearchFieldSearxngBaseUrl",
  zhipu_search_engine: "settings.webSearchFieldZhipuSearchEngine",
};

export function WebSearchSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data: settings, isLoading: isSettingsLoading } = useQuery({
    queryKey: ["web-search-settings"],
    queryFn: fetchWebSearchSettings,
  });
  const { data: providers = [], isLoading: isProvidersLoading } = useQuery({
    queryKey: ["web-search-providers"],
    queryFn: fetchWebSearchProviders,
    staleTime: 5 * 60 * 1000,
  });

  const [providerDraft, setProviderDraft] = useState("");
  const [extrasDraft, setExtrasDraft] = useState<Record<string, string>>({});
  const [apiKeyDraft, setApiKeyDraft] = useState("");
  const draftBaseProviderRef = useRef<string | null>(null);

  useEffect(() => {
    if (!settings) return;
    if (draftBaseProviderRef.current === settings.provider) return;
    draftBaseProviderRef.current = settings.provider;
    setProviderDraft(settings.provider);
    setExtrasDraft(settings.extras);
    setApiKeyDraft("");
  }, [settings]);

  const selectedProvider = useMemo(
    () => providers.find((provider) => provider.name === providerDraft),
    [providers, providerDraft],
  );

  const toggleMutation = useMutation({
    mutationFn: (enabled: boolean) => updateWebSearchSettings({ enabled }),
    onSuccess: (nextSettings) => {
      queryClient.setQueryData(["web-search-settings"], nextSettings);
      toast.success(t("settings.saved"));
    },
    onError: () => toast.error(t("settings.saveFailed")),
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!selectedProvider) return null;
      const extras: Record<string, string> = {};
      for (const field of selectedProvider.fields) {
        const value =
          field.fieldType === "select"
            ? (extrasDraft[field.key] ?? field.options[0] ?? "")
            : (extrasDraft[field.key] ?? "");
        if (value) extras[field.key] = value;
      }

      const request: WebSearchSettingsUpdateRequest = {
        provider: providerDraft,
        extras,
      };
      if (selectedProvider.requiresApiKey) {
        if (apiKeyDraft) request.api_key = apiKeyDraft;
      } else {
        request.api_key = "";
      }
      return updateWebSearchSettings(request);
    },
    onSuccess: (nextSettings) => {
      if (nextSettings) queryClient.setQueryData(["web-search-settings"], nextSettings);
      setApiKeyDraft("");
      toast.success(t("settings.saved"));
    },
    onError: () => toast.error(t("settings.saveFailed")),
  });

  const hasUnsavedApiKeyGap =
    selectedProvider?.requiresApiKey === true && !apiKeyDraft && !settings?.hasApiKey;
  const hasUnfilledRequiredField = selectedProvider?.fields.some(
    (field) =>
      field.required && field.fieldType === "text" && !(extrasDraft[field.key] ?? "").trim(),
  );

  if (isSettingsLoading || isProvidersLoading || !settings) {
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

  const renderProviderField = (field: WebSearchProviderField) => {
    const label = t(FIELD_LABEL_KEY_MAP[field.key] ?? field.key);
    if (field.fieldType === "select") {
      return (
        <Flex
          key={field.key}
          align="center"
          justify="between"
          gap="4"
        >
          <Text
            size="2"
            weight="medium"
          >
            {label}
          </Text>
          <LabeledSelect
            value={extrasDraft[field.key] ?? field.options[0] ?? ""}
            options={field.options.map((option) => ({ value: option, label: option }))}
            onChange={(value) => setExtrasDraft((prev) => ({ ...prev, [field.key]: value }))}
            disabled={saveMutation.isPending}
            triggerStyle={{ width: 160 }}
          />
        </Flex>
      );
    }
    return (
      <Flex
        key={field.key}
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
          value={extrasDraft[field.key] ?? ""}
          onChange={(event) =>
            setExtrasDraft((prev) => ({ ...prev, [field.key]: event.target.value }))
          }
          placeholder={
            field.key === "searxng_base_url" ? t("settings.webSearchBaseUrlPlaceholder") : undefined
          }
          disabled={saveMutation.isPending}
          style={{ width: 260 }}
        />
      </Flex>
    );
  };

  return (
    <Box>
      <Flex
        direction="column"
        gap="4"
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
            <Text
              size="2"
              weight="medium"
            >
              {t("settings.webSearchEnabled")}
            </Text>
            <Text
              size="1"
              color="gray"
            >
              {t("settings.webSearchEnabledHint")}
            </Text>
          </Flex>
          <Switch
            checked={settings.enabled}
            aria-label={t("settings.webSearchEnabled")}
            onCheckedChange={(checked) => toggleMutation.mutate(checked)}
          />
        </Flex>

        <Flex
          align="center"
          justify="between"
          gap="4"
        >
          <Text
            size="2"
            weight="medium"
          >
            {t("settings.webSearchProvider")}
          </Text>
          <LabeledSelect
            value={providerDraft}
            placeholder={t("settings.webSearchProviderPlaceholder")}
            options={providers.map((provider) => ({
              value: provider.name,
              label: provider.name,
            }))}
            onChange={(provider) => {
              setProviderDraft(provider);
              setExtrasDraft({});
              setApiKeyDraft("");
            }}
            disabled={saveMutation.isPending}
            triggerStyle={{ width: 160 }}
          />
        </Flex>

        {selectedProvider?.fields.map(renderProviderField)}

        {selectedProvider?.requiresApiKey ? (
          <Flex
            direction="column"
            gap="2"
          >
            <Text
              size="2"
              weight="medium"
              color="gray"
            >
              {t("settings.webSearchApiKey")}
            </Text>
            <TextField.Root
              type="password"
              value={apiKeyDraft}
              onChange={(event) => setApiKeyDraft(event.target.value)}
              placeholder={
                settings.hasApiKey
                  ? t("settings.webSearchApiKeyPlaceholderEdit")
                  : t("settings.webSearchApiKeyPlaceholder")
              }
              disabled={saveMutation.isPending}
              style={{ width: 260 }}
            />
            {settings.hasApiKey ? (
              <Text
                size="1"
                color="gray"
              >
                {t("settings.webSearchApiKeyEditHint")}
              </Text>
            ) : null}
          </Flex>
        ) : null}

        <Box>
          <Button
            disabled={
              saveMutation.isPending ||
              !providerDraft ||
              hasUnsavedApiKeyGap ||
              Boolean(hasUnfilledRequiredField)
            }
            onClick={() => saveMutation.mutate()}
          >
            {saveMutation.isPending ? <Spinner size={18} /> : null}
            {t("settings.webSearchSave")}
          </Button>
        </Box>
      </Flex>
    </Box>
  );
}
