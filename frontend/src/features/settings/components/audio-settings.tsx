import { Badge, Box, Button, Flex, IconButton, Switch, Text, TextField } from "@radix-ui/themes";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Download, Trash2, Undo2 } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Spinner, toast } from "@/components";
import { LabeledSelect } from "@/components/select";
import { apiClient } from "@/lib/api-client";

import { ASRProviderIcon } from "../lib/asr-provider-icons";
import { ASR_DEFAULTS, ASR_PROVIDERS, fetchASRSettings, saveASRSettings } from "../lib/audio-api";
import type { ASRProvider, ASRProviderConfig, ASRSettings } from "../lib/audio-api";

import "./audio-settings.css";

function AudioSettingRow({
  label,
  description,
  children,
  compact = false,
}: {
  label: string;
  description: string;
  children: ReactNode;
  compact?: boolean;
}) {
  return (
    <Flex
      align="center"
      justify="between"
      gap="4"
      className={`audio-settings-row${compact ? " audio-settings-row--compact" : ""}`}
    >
      <Flex
        direction="column"
        gap="1"
        className="audio-settings-label"
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
      <div className="audio-settings-control">{children}</div>
    </Flex>
  );
}

export function AudioSettings() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["asr-settings"], queryFn: fetchASRSettings });
  const status = useQuery<{
    sensevoice_installed: boolean;
    sensevoice_ready: boolean;
  }>({
    queryKey: ["asr-status"],
    queryFn: async () => (await apiClient.get("/audio/local-status")).data,
  });
  const [draft, setDraft] = useState<ASRSettings | null>(null);
  const [keys, setKeys] = useState<Partial<Record<ASRProvider, string>>>({});
  const [busy, setBusy] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const value = draft ?? query.data;
  if (!value)
    return (
      <Flex
        align="center"
        justify="center"
        style={{ height: "100%" }}
      >
        {query.isError ? (
          <Text
            role="alert"
            color="gray"
          >
            {t("speech.loadFailed")}
          </Text>
        ) : (
          <Spinner size={18} />
        )}
      </Flex>
    );
  const config = value.providers[value.provider];
  const clearingKey = Boolean(config.has_api_key) && keys[value.provider] === "";
  const local = value.provider === "sensevoice";
  const disabled = busy || toggling;
  const setField = (field: keyof ASRProviderConfig, text: string) =>
    setDraft({
      ...value,
      providers: { ...value.providers, [value.provider]: { ...config, [field]: text } },
    });

  async function toggle(enabled: boolean) {
    if (!query.data) return;
    const previousDraft = draft;
    setToggling(true);
    setDraft({ ...(draft ?? query.data), enabled });
    try {
      const saved = await saveASRSettings({ ...query.data, enabled });
      client.setQueryData(["asr-settings"], saved);
      setDraft(previousDraft ? { ...previousDraft, enabled } : null);
      toast.success(t("settings.saved"));
    } catch {
      setDraft(previousDraft);
      toast.error(t("settings.saveFailed"));
    } finally {
      setToggling(false);
    }
  }

  async function save(prepare = false) {
    if (!value) return;
    setBusy(true);
    try {
      const saved = await saveASRSettings(value, keys[value.provider]);
      client.setQueryData(["asr-settings"], saved);
      setDraft(null);
      setKeys((current) => {
        const next = { ...current };
        delete next[value.provider];
        return next;
      });
      if (prepare) {
        setPreparing(true);
        await apiClient.post("/audio/prepare", undefined, { timeout: 610000 });
      }
      await client.invalidateQueries({ queryKey: ["asr-status"] });
      toast.success(t(prepare ? "speech.prepared" : "settings.saved"));
    } catch {
      toast.error(t(prepare ? "speech.prepareFailed" : "settings.saveFailed"));
    } finally {
      setBusy(false);
      setPreparing(false);
    }
  }

  const field = (
    name: keyof ASRProviderConfig,
    label: string,
    description: string,
    placeholder = "",
  ) => (
    <AudioSettingRow
      label={label}
      description={description}
    >
      <TextField.Root
        aria-label={label}
        value={String(config[name] ?? "")}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(event) => setField(name, event.target.value)}
      />
    </AudioSettingRow>
  );

  return (
    <Box className="audio-settings">
      <Flex
        direction="column"
        gap="5"
      >
        <AudioSettingRow
          label={t("speech.enable")}
          description={t("speech.enabledHint")}
          compact
        >
          <Switch
            checked={value.enabled}
            onCheckedChange={(enabled) => void toggle(enabled)}
            disabled={disabled}
            aria-label={t("speech.enable")}
          />
        </AudioSettingRow>
        <AudioSettingRow
          label={t("speech.provider")}
          description={t("speech.providerHint")}
          compact
        >
          <LabeledSelect
            value={value.provider}
            triggerAriaLabel={t("speech.provider")}
            options={ASR_PROVIDERS.map((provider) => ({
              value: provider,
              label: t(`speech.providers.${provider}`),
              prefix: <ASRProviderIcon provider={provider} />,
            }))}
            onChange={(provider) => setDraft({ ...value, provider: provider as ASRProvider })}
            disabled={disabled}
            triggerClassName="audio-settings-provider-select"
          />
        </AudioSettingRow>
        <AudioSettingRow
          label={t("speech.language")}
          description={t(
            value.provider === "azure"
              ? "speech.azureLanguage"
              : value.provider === "sensevoice"
                ? "speech.languageHint"
                : "speech.languageAutoHint",
          )}
        >
          <TextField.Root
            aria-label={t("speech.language")}
            value={value.language}
            disabled={disabled}
            onChange={(event) => setDraft({ ...value, language: event.target.value })}
            placeholder="auto"
          />
        </AudioSettingRow>

        {!local ? (
          <>
            {field(
              "base_url",
              t("speech.baseUrl"),
              t("speech.baseUrlHint"),
              ASR_DEFAULTS[value.provider]?.[0],
            )}
            {value.provider !== "azure"
              ? field(
                  "model",
                  t("speech.model"),
                  t("speech.modelHint"),
                  ASR_DEFAULTS[value.provider]?.[1],
                )
              : null}
            <AudioSettingRow
              label="API Key"
              description={t(
                clearingKey
                  ? "speech.keyWillClear"
                  : config.has_api_key
                    ? "speech.keySaved"
                    : "speech.keyPlaceholder",
              )}
            >
              <TextField.Root
                type="password"
                autoComplete="new-password"
                aria-label="ASR API Key"
                disabled={disabled}
                value={keys[value.provider] ?? ""}
                placeholder={t("speech.keyPlaceholder")}
                onChange={(event) => setKeys({ ...keys, [value.provider]: event.target.value })}
              >
                {config.has_api_key ? (
                  <TextField.Slot side="right">
                    <IconButton
                      type="button"
                      size="1"
                      variant="ghost"
                      color="gray"
                      disabled={disabled}
                      aria-label={t(clearingKey ? "speech.keepKey" : "speech.clearKey")}
                      title={t(clearingKey ? "speech.keepKey" : "speech.clearKey")}
                      onClick={() =>
                        setKeys((current) => {
                          const next = { ...current };
                          if (clearingKey) delete next[value.provider];
                          else next[value.provider] = "";
                          return next;
                        })
                      }
                    >
                      {clearingKey ? <Undo2 size={14} /> : <Trash2 size={14} />}
                    </IconButton>
                  </TextField.Slot>
                ) : null}
              </TextField.Root>
            </AudioSettingRow>
            <Text
              size="1"
              color="gray"
            >
              {t("speech.cloudNotice")}
            </Text>
          </>
        ) : (
          <>
            <AudioSettingRow
              label={t("speech.localModel")}
              description={t("speech.modelDownloadHint")}
            >
              <Flex
                align="center"
                justify="end"
                gap="3"
                wrap="wrap"
              >
                <Badge
                  size="1"
                  variant="soft"
                  color={status.data?.sensevoice_ready ? "green" : "gray"}
                  role="status"
                >
                  {t(
                    status.isPending
                      ? "common.loading"
                      : status.isError
                        ? "speech.statusUnavailable"
                        : status.data?.sensevoice_ready
                          ? "speech.ready"
                          : "speech.notReady",
                  )}
                </Badge>
                <Button
                  size="2"
                  variant="soft"
                  disabled={disabled}
                  onClick={() => void save(true)}
                >
                  {preparing ? <Spinner size={18} /> : <Download size={14} />}
                  {t("speech.prepareModel")}
                </Button>
              </Flex>
            </AudioSettingRow>
            {status.data && !status.data.sensevoice_installed ? (
              <Text
                size="1"
                color="orange"
              >
                {t("speech.installExtra")}
              </Text>
            ) : null}
            <details
              className="audio-settings-advanced"
              key="sensevoice-paths"
            >
              <summary>
                <ChevronRight size={16} />
                <Text
                  size="2"
                  weight="medium"
                >
                  {t("speech.customPaths")}
                </Text>
                <Text
                  size="1"
                  color="gray"
                >
                  {t("speech.optional")}
                </Text>
              </summary>
              <Flex
                direction="column"
                gap="4"
                pt="4"
              >
                {field(
                  "model_path",
                  t("speech.modelPath"),
                  t("speech.modelPathHint"),
                  "/path/to/model.int8.onnx",
                )}
                {field(
                  "tokens_path",
                  t("speech.tokensPath"),
                  t("speech.pathHint"),
                  "/path/to/tokens.txt",
                )}
                {field(
                  "vad_path",
                  t("speech.vadPath"),
                  t("speech.pathHint"),
                  "/path/to/silero_vad.onnx",
                )}
              </Flex>
            </details>
          </>
        )}
        <Box>
          <Button
            disabled={disabled}
            onClick={() => void save()}
          >
            {busy && !preparing ? <Spinner size={18} /> : null}
            {t("common.save")}
          </Button>
        </Box>
        {preparing ? (
          <Text
            size="1"
            color="gray"
            role="status"
          >
            {t("speech.preparing")}
          </Text>
        ) : null}
      </Flex>
    </Box>
  );
}
