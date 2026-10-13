import { Badge, Box, Button, Flex, IconButton, Link, Text, TextField } from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { Copy, ExternalLink, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner, toast } from "@/components";
import { LabeledSelect } from "@/components/select";

import "./tunnels-settings.css";

import { fetchTunnel, startTunnel, stopTunnel, type TunnelProvider } from "../lib/tunnels-api";

function TunnelSettingLabel({ label, description }: { label: string; description: string }) {
  return (
    <Flex
      direction="column"
      gap="1"
      className="tunnel-setting-label"
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
  );
}

export function TunnelsSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [provider, setProvider] = useState<TunnelProvider>("cloudflare");
  const [mode, setMode] = useState<"quick" | "managed-remote">("quick");
  const [token, setToken] = useState("");
  const [hostname, setHostname] = useState("");
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["tunnels"],
    queryFn: fetchTunnel,
    refetchInterval: 2000,
  });
  const mutation = useMutation({
    mutationFn: (action: "start" | "stop") =>
      action === "stop"
        ? stopTunnel()
        : startTunnel({
            provider,
            mode,
            ...(mode === "managed-remote" ? { token, hostname: hostname.trim() } : {}),
          }),
    onSuccess: () => {
      setToken("");
      void queryClient.invalidateQueries({ queryKey: ["tunnels"] });
    },
  });
  const active = data?.status === "starting" || data?.status === "running";
  const busy = mutation.isPending;
  const mutationDetail = axios.isAxiosError(mutation.error)
    ? mutation.error.response?.data?.detail
    : null;
  const errorMessage =
    typeof mutationDetail === "string" ? mutationDetail : t("settings.tunnelRequestFailed");

  async function copyUrl() {
    try {
      await navigator.clipboard.writeText(data?.url ?? "");
      toast.success(t("settings.tunnelCopied"));
    } catch {
      toast.error(t("settings.tunnelCopyFailed"));
    }
  }

  if (isLoading)
    return (
      <Flex
        align="center"
        justify="center"
        style={{ height: "100%" }}
      >
        <Spinner size={18} />
      </Flex>
    );
  if (error || !data)
    return (
      <Flex
        direction="column"
        gap="3"
      >
        <Text>{t("settings.tunnelRequestFailed")}</Text>
        <Button onClick={() => void refetch()}>{t("settings.tunnelRefresh")}</Button>
      </Flex>
    );

  const binary = provider === "cloudflare" ? "cloudflared" : "ngrok";
  const canStart =
    data.auth_enabled &&
    data.frontend_available &&
    data.providers[provider] &&
    (mode !== "managed-remote" || (token.trim() && hostname.trim()));

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
          className="tunnel-setting-row"
        >
          <TunnelSettingLabel
            label={t("settings.tunnelConnectionStatus")}
            description={t("settings.tunnelDescription")}
          />
          <Badge
            variant="soft"
            color={data.status === "running" ? "green" : data.status === "error" ? "red" : "gray"}
          >
            {t(`settings.tunnelStatus_${data.status}`)}
            {active ? ` · ${data.provider === "cloudflare" ? "Cloudflare" : "Ngrok"}` : ""}
          </Badge>
        </Flex>
        <Flex
          align="center"
          justify="between"
          gap="4"
          className="tunnel-setting-row"
        >
          <TunnelSettingLabel
            label={t("settings.tunnelProvider")}
            description={t("settings.tunnelProviderDescription")}
          />
          <LabeledSelect
            value={provider}
            options={[
              { value: "cloudflare", label: "Cloudflare" },
              { value: "ngrok", label: "Ngrok" },
            ]}
            onChange={(value) => {
              setProvider(value as TunnelProvider);
              setMode("quick");
            }}
            disabled={active || busy}
            triggerAriaLabel={t("settings.tunnelProvider")}
            triggerStyle={{ width: 160 }}
          />
        </Flex>
        <Flex
          align="center"
          justify="between"
          gap="4"
          className="tunnel-setting-row"
        >
          <TunnelSettingLabel
            label={t("settings.tunnelClient", { binary })}
            description={t(
              data.providers[provider] ? "settings.tunnelInstalled" : "settings.tunnelMissing",
              { binary },
            )}
          />
          <Flex
            align="center"
            gap="3"
            flexShrink="0"
          >
            <Link
              size="2"
              href={
                provider === "cloudflare"
                  ? "https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/"
                  : "https://ngrok.com/download"
              }
              target="_blank"
              rel="noreferrer"
            >
              {t("settings.tunnelInstallHelp")}
            </Link>
            <IconButton
              variant="ghost"
              color="gray"
              aria-label={t("settings.tunnelRefresh")}
              disabled={busy}
              onClick={() => void refetch()}
            >
              <RefreshCw size={16} />
            </IconButton>
          </Flex>
        </Flex>
        {provider === "ngrok" && (
          <Text
            size="1"
            color="gray"
          >
            {t("settings.tunnelNgrokHelp")}
          </Text>
        )}
        {provider === "cloudflare" && (
          <>
            <Flex
              align="center"
              justify="between"
              gap="4"
              className="tunnel-setting-row"
            >
              <TunnelSettingLabel
                label={t("settings.tunnelMode")}
                description={t("settings.tunnelModeDescription")}
              />
              <LabeledSelect
                value={mode}
                options={[
                  { value: "quick", label: t("settings.tunnelQuick") },
                  { value: "managed-remote", label: t("settings.tunnelManaged") },
                ]}
                onChange={(value) => setMode(value as typeof mode)}
                disabled={active || busy}
                triggerAriaLabel={t("settings.tunnelMode")}
                triggerStyle={{ width: 200 }}
              />
            </Flex>
            {mode === "managed-remote" && (
              <>
                <Flex
                  align="center"
                  justify="between"
                  gap="4"
                  className="tunnel-setting-row tunnel-setting-row--field"
                >
                  <TunnelSettingLabel
                    label={t("settings.tunnelHostname")}
                    description={t("settings.tunnelHostnameDescription")}
                  />
                  <TextField.Root
                    aria-label={t("settings.tunnelHostname")}
                    value={hostname}
                    placeholder="openfic.example.com"
                    disabled={active || busy}
                    onChange={(event) => setHostname(event.target.value)}
                    className="tunnel-setting-field"
                  />
                </Flex>
                <Flex
                  align="center"
                  justify="between"
                  gap="4"
                  className="tunnel-setting-row tunnel-setting-row--field"
                >
                  <TunnelSettingLabel
                    label={t("settings.tunnelToken")}
                    description={t("settings.tunnelTokenDescription")}
                  />
                  <TextField.Root
                    aria-label={t("settings.tunnelToken")}
                    type="password"
                    autoComplete="off"
                    value={token}
                    disabled={active || busy}
                    onChange={(event) => setToken(event.target.value)}
                    className="tunnel-setting-field"
                  />
                </Flex>
                <Text
                  size="1"
                  color="gray"
                >
                  {t("settings.tunnelManagedHelp")}
                </Text>
              </>
            )}
          </>
        )}
        {data.url && (
          <Flex
            align="center"
            justify="between"
            gap="4"
            className="tunnel-setting-row tunnel-setting-row--field"
          >
            <TunnelSettingLabel
              label={t("settings.tunnelUrl")}
              description={t("settings.tunnelUrlDescription")}
            />
            <Flex
              align="center"
              gap="2"
              className="tunnel-setting-url"
            >
              <TextField.Root
                readOnly
                value={data.url}
                aria-label={t("settings.tunnelUrl")}
                style={{ flex: 1, minWidth: 0 }}
              >
                <TextField.Slot side="right">
                  <IconButton
                    size="1"
                    variant="ghost"
                    color="gray"
                    aria-label={t("settings.tunnelCopy")}
                    onClick={() => void copyUrl()}
                  >
                    <Copy size={14} />
                  </IconButton>
                </TextField.Slot>
              </TextField.Root>
              <IconButton
                asChild
                variant="ghost"
                color="gray"
                aria-label={t("settings.tunnelOpen")}
              >
                <a
                  href={data.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <ExternalLink size={16} />
                </a>
              </IconButton>
            </Flex>
          </Flex>
        )}
        {!data.auth_enabled && (
          <Text
            size="1"
            color="amber"
          >
            {t("settings.tunnelAuthRequired")}
          </Text>
        )}
        {!data.frontend_available && (
          <Text
            size="1"
            color="amber"
          >
            {t("settings.tunnelFrontendRequired")}
          </Text>
        )}
        {(data.error || mutation.error) && (
          <Text
            role="alert"
            size="1"
            color="red"
          >
            {mutation.error ? errorMessage : t(`settings.tunnelError_${data.error}`)}
          </Text>
        )}
        <Box>
          <Button
            disabled={busy || (!active && !canStart)}
            color={active ? "red" : undefined}
            onClick={() => mutation.mutate(active ? "stop" : "start")}
          >
            {busy ? <Spinner size={18} /> : null}
            {t(active ? "settings.tunnelStop" : "settings.tunnelStart")}
          </Button>
        </Box>
        <Text
          size="1"
          color="gray"
        >
          {t("settings.tunnelLifetime")}
        </Text>
      </Flex>
    </Box>
  );
}
