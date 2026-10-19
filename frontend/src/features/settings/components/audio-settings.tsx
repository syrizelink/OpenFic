import { Button, Flex, Switch, Text, TextField } from "@radix-ui/themes";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { toast } from "@/components";
import { apiClient } from "@/lib/api-client";

import { ASR_DEFAULTS, ASR_PROVIDERS, fetchASRSettings, saveASRSettings } from "../lib/audio-api";
import type { ASRProvider, ASRProviderConfig, ASRSettings } from "../lib/audio-api";

export function AudioSettings() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["asr-settings"], queryFn: fetchASRSettings });
  const status = useQuery<{
    sensevoice_installed: boolean;
    whisper_installed: boolean;
    sensevoice_ready: boolean;
  }>({
    queryKey: ["asr-status"],
    queryFn: async () => (await apiClient.get("/audio/local-status")).data,
  });
  const [draft, setDraft] = useState<ASRSettings | null>(null);
  const [keys, setKeys] = useState<Partial<Record<ASRProvider, string>>>({});
  const [busy, setBusy] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const value = draft ?? query.data;
  if (!value)
    return <Text role="status">{t(query.isError ? "speech.loadFailed" : "common.loading")}</Text>;
  const config = value.providers[value.provider];
  const local = value.provider === "sensevoice" || value.provider === "whisper";
  const setField = (field: keyof ASRProviderConfig, text: string) =>
    setDraft({
      ...value,
      providers: { ...value.providers, [value.provider]: { ...config, [field]: text } },
    });
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
  const field = (name: keyof ASRProviderConfig, label: string, placeholder = "") => (
    <label>
      <Text
        as="div"
        size="2"
        mb="1"
      >
        {label}
      </Text>
      <TextField.Root
        aria-label={label}
        value={String(config[name] ?? "")}
        placeholder={placeholder}
        onChange={(event) => setField(name, event.target.value)}
      />
    </label>
  );
  return (
    <Flex
      direction="column"
      gap="4"
      style={{ maxWidth: 720 }}
    >
      <Text
        size="4"
        weight="bold"
      >
        {t("speech.title")}
      </Text>
      <Text
        size="2"
        color="gray"
      >
        {t("speech.description")}
      </Text>
      <fieldset
        disabled={busy}
        style={{ border: 0, padding: 0, margin: 0 }}
      >
        <Flex
          direction="column"
          gap="4"
        >
          <Flex
            align="center"
            gap="3"
          >
            <Switch
              checked={value.enabled}
              onCheckedChange={(enabled) => setDraft({ ...value, enabled })}
              aria-label={t("speech.enable")}
            />
            <Text size="2">{t("speech.enable")}</Text>
          </Flex>
          <label>
            <Text
              as="div"
              size="2"
              mb="1"
            >
              {t("speech.provider")}
            </Text>
            <select
              aria-label={t("speech.provider")}
              value={value.provider}
              onChange={(event) =>
                setDraft({ ...value, provider: event.target.value as ASRProvider })
              }
            >
              {ASR_PROVIDERS.map((provider) => (
                <option
                  key={provider}
                  value={provider}
                >
                  {t(`speech.providers.${provider}`)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <Text
              as="div"
              size="2"
              mb="1"
            >
              {t("speech.language")}
            </Text>
            <TextField.Root
              aria-label={t("speech.language")}
              value={value.language}
              onChange={(event) => setDraft({ ...value, language: event.target.value })}
              placeholder="auto / zh / en / zh-CN"
            />
          </label>
          <Text
            size="1"
            color="gray"
          >
            {t(value.provider === "azure" ? "speech.azureLanguage" : "speech.languageHint")}
          </Text>
          {!local ? (
            <>
              {field("base_url", t("speech.baseUrl"), ASR_DEFAULTS[value.provider]?.[0])}
              {value.provider !== "azure"
                ? field("model", t("speech.model"), ASR_DEFAULTS[value.provider]?.[1])
                : null}
              <label>
                <Text
                  as="div"
                  size="2"
                  mb="1"
                >
                  API Key
                </Text>
                <TextField.Root
                  type="password"
                  autoComplete="new-password"
                  aria-label="ASR API Key"
                  value={keys[value.provider] ?? ""}
                  placeholder={t(config.has_api_key ? "speech.keySaved" : "speech.keyPlaceholder")}
                  onChange={(event) => setKeys({ ...keys, [value.provider]: event.target.value })}
                />
              </label>
              {config.has_api_key ? (
                <Button
                  variant="soft"
                  color="red"
                  onClick={() => setKeys({ ...keys, [value.provider]: "" })}
                >
                  {t("speech.clearKey")}
                </Button>
              ) : null}
              <Text
                size="1"
                color="gray"
              >
                {t("speech.cloudNotice")}
              </Text>
            </>
          ) : value.provider === "sensevoice" ? (
            <>
              <Text
                size="2"
                role="status"
              >
                {t(status.data?.sensevoice_ready ? "speech.modelReady" : "speech.modelMissing")}
              </Text>
              {!status.data?.sensevoice_installed ? (
                <Text
                  size="2"
                  color="orange"
                >
                  {t("speech.installExtra")}
                </Text>
              ) : null}
              <Text
                size="1"
                color="gray"
              >
                {t("speech.sensevoiceHint")}
              </Text>
              {field("model_path", t("speech.modelPath"))}
              {field("tokens_path", t("speech.tokensPath"))}
              {field("vad_path", t("speech.vadPath"))}
              <Button
                variant="soft"
                onClick={() => void save(true)}
              >
                {t("speech.prepare")}
              </Button>
            </>
          ) : (
            <>
              {field("model", t("speech.whisperPath"), "/absolute/path/to/faster-whisper-small")}
              <Text
                size="2"
                color="gray"
              >
                {t("speech.whisperHint")}
              </Text>
              {!status.data?.whisper_installed ? (
                <Text
                  size="2"
                  color="orange"
                >
                  {t("speech.installExtra")}
                </Text>
              ) : null}
            </>
          )}
          <Button onClick={() => void save()}>{t("common.save")}</Button>
        </Flex>
      </fieldset>
      {busy ? (
        <Text role="status">{t(preparing ? "speech.preparing" : "speech.saving")}</Text>
      ) : null}
    </Flex>
  );
}
