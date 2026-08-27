import { Box, Button, Flex, Switch, Text, TextField } from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner, toast } from "@/components";
import { LabeledSelect } from "@/components/select";

import { ProviderIcon } from "../lib/provider-icons";
import {
  fetchWebSearchProviders,
  fetchWebSearchSettings,
  updateWebSearchSettings,
} from "../lib/web-search-api";
import type { WebSearchProviderField, WebSearchSettingsUpdateRequest } from "../lib/web-search-api";

const FIELD_LABEL_KEY_MAP: Record<string, string> = {
  ddgs_backend: "settings.webSearchFieldDdgsBackend",
  jina_base_url: "settings.webSearchFieldJinaBaseUrl",
  searxng_base_url: "settings.webSearchFieldSearxngBaseUrl",
  zhipu_search_engine: "settings.webSearchFieldZhipuSearchEngine",
};

const FIELD_DEFAULT_VALUE_MAP: Record<string, string> = {
  jina_base_url: "https://s.jina.ai/",
};

function getProviderFieldValue(
  field: WebSearchProviderField,
  draft: Record<string, string>,
): string {
  return draft[field.key] ?? FIELD_DEFAULT_VALUE_MAP[field.key] ?? field.options[0] ?? "";
}

function parseDomainFilters(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((domain) => domain.trim())
    .filter(Boolean);
}

const FIELD_OPTION_LABEL_KEY_MAP: Record<string, Record<string, string>> = {
  ddgs_backend: {
    auto: "settings.webSearchDdgsBackendAuto",
    brave: "settings.webSearchDdgsBackendBrave",
    duckduckgo: "settings.webSearchDdgsBackendDuckDuckGo",
    grokipedia: "settings.webSearchDdgsBackendGrokipedia",
    mojeek: "settings.webSearchDdgsBackendMojeek",
    wikipedia: "settings.webSearchDdgsBackendWikipedia",
    yahoo: "settings.webSearchDdgsBackendYahoo",
    startpage: "settings.webSearchDdgsBackendStartpage",
  },
};

const PROVIDER_LABEL_KEY_MAP: Record<string, string> = {
  brave: "settings.webSearchProviderBrave",
  ddgs: "settings.webSearchProviderDdgs",
  exa: "settings.webSearchProviderExa",
  jina: "settings.webSearchProviderJina",
  perplexity: "settings.webSearchProviderPerplexity",
  searxng: "settings.webSearchProviderSearxng",
  serper: "settings.webSearchProviderSerper",
  tavily: "settings.webSearchProviderTavily",
  zhipu: "settings.webSearchProviderZhipu",
};

const PROVIDER_ICON_PATH_MAP: Record<string, string> = {
  brave: "/provider-icons/web-search/brave.svg",
  exa: "/provider-icons/web-search/exa.svg",
  jina: "/provider-icons/web-search/jina.svg",
  perplexity: "/provider-icons/web-search/perplexity.svg",
  searxng: "/provider-icons/web-search/searxng.svg",
  serper: "/provider-icons/web-search/serper.svg",
  tavily: "/provider-icons/web-search/tavily.svg",
  zhipu: "/provider-icons/web-search/zhipu.svg",
};
const MASKED_API_KEY_VALUE = "••••••••";

function WebSearchProviderIcon({ providerName }: { providerName: string }) {
  const iconPath = PROVIDER_ICON_PATH_MAP[providerName];
  if (!iconPath) return null;

  return (
    <ProviderIcon
      iconPath={iconPath}
      preserveColors
      size={16}
    />
  );
}

interface WebSearchSettingLabelProps {
  label: string;
  description: string;
  labelColor?: "gray";
}

function WebSearchSettingLabel({ label, description, labelColor }: WebSearchSettingLabelProps) {
  return (
    <Flex
      direction="column"
      gap="1"
    >
      <Text
        size="2"
        weight="medium"
        color={labelColor}
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
  const [apiKeyDrafts, setApiKeyDrafts] = useState<Record<string, string>>({});
  const [maxResultsDraft, setMaxResultsDraft] = useState("");
  const [domainFiltersDraft, setDomainFiltersDraft] = useState("");
  const draftBaseProviderRef = useRef<string | null>(null);

  useEffect(() => {
    if (!settings) return;
    if (draftBaseProviderRef.current === settings.provider) return;
    draftBaseProviderRef.current = settings.provider;
    setProviderDraft(settings.provider);
    setExtrasDraft(settings.extras);
    setApiKeyDrafts({});
    setMaxResultsDraft(String(settings.maxResults));
    setDomainFiltersDraft(settings.domainFilters.join(", "));
  }, [settings]);

  const selectedProvider = useMemo(
    () => providers.find((provider) => provider.name === providerDraft),
    [providers, providerDraft],
  );
  const apiKeyDraft = apiKeyDrafts[providerDraft] ?? "";
  const hasApiKey = Boolean(settings?.hasApiKeys[providerDraft]);
  const apiKeyInputValue = hasApiKey && !apiKeyDraft ? MASKED_API_KEY_VALUE : apiKeyDraft;
  const maxResults = Number(maxResultsDraft);
  const hasInvalidMaxResults = !Number.isInteger(maxResults) || maxResults < 1 || maxResults > 20;

  const getProviderLabel = (providerName: string) =>
    t(PROVIDER_LABEL_KEY_MAP[providerName] ?? providerName);

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
      if (!selectedProvider || hasInvalidMaxResults) return null;
      const extras: Record<string, string> = {};
      for (const field of selectedProvider.fields) {
        const value = getProviderFieldValue(field, extrasDraft);
        if (value) extras[field.key] = value;
      }

      const request: WebSearchSettingsUpdateRequest = {
        provider: providerDraft,
        max_results: maxResults,
        domain_filters: parseDomainFilters(domainFiltersDraft),
        extras,
      };
      if (selectedProvider.requiresApiKey) {
        if (apiKeyDraft) request.api_key = apiKeyDraft;
      }
      return updateWebSearchSettings(request);
    },
    onSuccess: (nextSettings) => {
      if (nextSettings) {
        queryClient.setQueryData(["web-search-settings"], nextSettings);
        setMaxResultsDraft(String(nextSettings.maxResults));
        setDomainFiltersDraft(nextSettings.domainFilters.join(", "));
      }
      setApiKeyDrafts((prev) => {
        const next = { ...prev };
        delete next[providerDraft];
        return next;
      });
      toast.success(t("settings.saved"));
    },
    onError: () => toast.error(t("settings.saveFailed")),
  });

  const hasUnsavedApiKeyGap =
    selectedProvider?.requiresApiKey === true && !apiKeyDraft && !hasApiKey;
  const hasUnfilledRequiredField = selectedProvider?.fields.some(
    (field) =>
      field.required &&
      field.fieldType === "text" &&
      !getProviderFieldValue(field, extrasDraft).trim(),
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
          <WebSearchSettingLabel
            label={label}
            description={t("settings.webSearchProviderSettingsDescription")}
          />
          <LabeledSelect
            value={getProviderFieldValue(field, extrasDraft)}
            options={field.options.map((option) => ({
              value: option,
              label: t(FIELD_OPTION_LABEL_KEY_MAP[field.key]?.[option] ?? option),
            }))}
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
        align="center"
        justify="between"
        gap="4"
      >
        <WebSearchSettingLabel
          label={label}
          description={t("settings.webSearchProviderSettingsDescription")}
          labelColor="gray"
        />
        <TextField.Root
          value={getProviderFieldValue(field, extrasDraft)}
          onChange={(event) =>
            setExtrasDraft((prev) => ({ ...prev, [field.key]: event.target.value }))
          }
          placeholder={
            field.key === "searxng_base_url"
              ? t("settings.webSearchBaseUrlPlaceholder")
              : field.key === "jina_base_url"
                ? t("settings.webSearchJinaBaseUrlPlaceholder")
                : undefined
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
          <WebSearchSettingLabel
            label={t("settings.webSearchProvider")}
            description={t("settings.webSearchProviderDescription")}
          />
          <LabeledSelect
            value={providerDraft}
            placeholder={t("settings.webSearchProviderPlaceholder")}
            options={providers.map((provider) => ({
              value: provider.name,
              label: getProviderLabel(provider.name),
              prefix: <WebSearchProviderIcon providerName={provider.name} />,
            }))}
            onChange={(provider) => {
              setProviderDraft(provider);
              setExtrasDraft({});
            }}
            disabled={saveMutation.isPending}
            triggerStyle={{ width: 160 }}
          />
        </Flex>

        {selectedProvider?.fields.map(renderProviderField)}

        {selectedProvider?.requiresApiKey ? (
          <Flex
            align="center"
            justify="between"
            gap="4"
          >
            <WebSearchSettingLabel
              label={t("settings.webSearchApiKey")}
              description={t("settings.webSearchProviderSettingsDescription")}
              labelColor="gray"
            />
            <Flex
              direction="column"
              gap="1"
            >
              <TextField.Root
                type="password"
                value={apiKeyInputValue}
                onFocus={() => {
                  if (hasApiKey && !apiKeyDraft) {
                    setApiKeyDrafts((prev) => ({ ...prev, [providerDraft]: "" }));
                  }
                }}
                onChange={(event) =>
                  setApiKeyDrafts((prev) => ({ ...prev, [providerDraft]: event.target.value }))
                }
                placeholder={t("settings.webSearchApiKeyPlaceholder")}
                disabled={saveMutation.isPending}
                style={{ width: 260 }}
              />
            </Flex>
          </Flex>
        ) : null}

        <Flex
          align="center"
          justify="between"
          gap="4"
        >
          <WebSearchSettingLabel
            label={t("settings.webSearchMaxResults")}
            description={t("settings.webSearchMaxResultsDescription")}
          />
          <TextField.Root
            type="number"
            min={1}
            max={20}
            value={maxResultsDraft}
            onChange={(event) => setMaxResultsDraft(event.target.value)}
            disabled={saveMutation.isPending}
            style={{ width: 160 }}
          />
        </Flex>

        <Flex
          align="center"
          justify="between"
          gap="4"
        >
          <WebSearchSettingLabel
            label={t("settings.webSearchDomainFilters")}
            description={t("settings.webSearchDomainFiltersDescription")}
          />
          <TextField.Root
            value={domainFiltersDraft}
            onChange={(event) => setDomainFiltersDraft(event.target.value)}
            placeholder={t("settings.webSearchDomainFiltersPlaceholder")}
            disabled={saveMutation.isPending}
            style={{ width: 260 }}
          />
        </Flex>

        <Box>
          <Button
            disabled={
              saveMutation.isPending ||
              !providerDraft ||
              hasUnsavedApiKeyGap ||
              Boolean(hasUnfilledRequiredField) ||
              hasInvalidMaxResults
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
