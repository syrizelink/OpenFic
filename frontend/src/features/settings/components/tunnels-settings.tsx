import {
  Badge,
  Box,
  Button,
  Callout,
  Dialog,
  Flex,
  IconButton,
  Link,
  Text,
  TextField,
} from "@radix-ui/themes";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { Copy, ExternalLink, Info, QrCode as QrCodeIcon, RefreshCw } from "lucide-react";
import QRCodeStyling from "qr-code-styling";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Trans, useTranslation } from "react-i18next";

import { Spinner, toast } from "@/components";
import { LabeledSelect } from "@/components/select";

import "./tunnels-settings.css";

import { TUNNEL_STATUS_QUERY_KEY, useTunnelStatus } from "@/lib/tunnel-status";

import { ProviderIcon } from "../lib/provider-icons";
import {
  startTunnel,
  stopTunnel,
  updateTunnelConfig,
  type TunnelConfigUpdate,
  type TunnelMode,
  type TunnelProvider,
  type TunnelStatus,
} from "../lib/tunnels-api";

const TUNNEL_PROVIDER_ICON_PATHS: Record<TunnelProvider, string> = {
  cloudflare: "/provider-icons/tunnel/cloudflare.svg",
  ngrok: "/provider-icons/tunnel/ngrok.svg",
};
const TUNNEL_CLIENT_NAMES: Record<TunnelProvider, string> = {
  cloudflare: "Cloudflared",
  ngrok: "Ngrok",
};

function TunnelProviderIcon({ provider }: { provider: TunnelProvider }) {
  return (
    <ProviderIcon
      iconPath={TUNNEL_PROVIDER_ICON_PATHS[provider]}
      preserveColors
      size={18}
    />
  );
}

function TunnelSettingLabel({ label, description }: { label: string; description?: string }) {
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
      {description ? (
        <Text
          size="1"
          color="gray"
        >
          {description}
        </Text>
      ) : null}
    </Flex>
  );
}

function TunnelInfoCallout({ children }: { children: ReactNode }) {
  return (
    <Callout.Root
      color="blue"
      size="1"
      className="tunnel-info-callout"
    >
      <Callout.Icon>
        <Info size={14} />
      </Callout.Icon>
      <Callout.Text size="1">{children}</Callout.Text>
    </Callout.Root>
  );
}

function TunnelQrCode({ url }: { url: string }) {
  const { t } = useTranslation();
  const qrCodeContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = qrCodeContainerRef.current;
    if (!container) return;

    const qrCode = new QRCodeStyling({
      type: "svg",
      width: 280,
      height: 280,
      data: url,
      image: "/pwa-icons/icon-192.png",
      margin: 12,
      qrOptions: {
        errorCorrectionLevel: "H",
      },
      imageOptions: {
        hideBackgroundDots: true,
        imageSize: 0.3,
        margin: 8,
        saveAsBlob: false,
      },
      dotsOptions: {
        type: "dots",
        color: "#111827",
      },
      cornersSquareOptions: {
        type: "extra-rounded",
        color: "#111827",
      },
      cornersDotOptions: {
        type: "dot",
        color: "#111827",
      },
      backgroundOptions: {
        color: "#ffffff",
      },
    });

    qrCode.append(container);

    return () => container.replaceChildren();
  }, [url]);

  return (
    <Box
      ref={qrCodeContainerRef}
      className="tunnel-qr-dialog-code"
      role="img"
      aria-label={t("settings.tunnelQrCode")}
    />
  );
}

function TunnelQrCodeDialog({
  url,
  open,
  onOpenChange,
}: {
  url: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();

  return (
    <Dialog.Root
      open={open}
      onOpenChange={onOpenChange}
    >
      <Dialog.Content
        className="tunnel-qr-dialog-content"
        maxWidth="360px"
      >
        <Dialog.Title>{t("settings.tunnelQrCodeTitle")}</Dialog.Title>
        <Dialog.Description
          className="tunnel-qr-dialog-description"
          size="2"
          color="gray"
        >
          {t("settings.tunnelQrCodeDescription")}
        </Dialog.Description>
        <TunnelQrCode url={url} />
        <Flex
          mt="4"
          justify="end"
        >
          <Dialog.Close>
            <Button
              color="gray"
              variant="soft"
            >
              {t("common.close")}
            </Button>
          </Dialog.Close>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

export function TunnelsSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [provider, setProvider] = useState<TunnelProvider>("cloudflare");
  const [mode, setMode] = useState<TunnelMode>("quick");
  const [token, setToken] = useState("");
  const [hostname, setHostname] = useState("");
  const [hasSavedToken, setHasSavedToken] = useState(false);
  const [isRefreshAnimationActive, setIsRefreshAnimationActive] = useState(false);
  const [isQrDialogOpen, setIsQrDialogOpen] = useState(false);
  const hasHydratedConfigRef = useRef(false);
  const { data, isLoading, isFetching, isFetchedAfterMount, error, refetch } = useTunnelStatus();

  useEffect(() => {
    if (!data?.config || hasHydratedConfigRef.current) return;
    hasHydratedConfigRef.current = true;
    setProvider(data.config.provider);
    setMode(data.config.mode);
    setHostname(data.config.hostname ?? "");
    setHasSavedToken(data.config.token_configured);
  }, [data]);

  function handleRefresh() {
    setIsRefreshAnimationActive(true);
    void refetch();
  }

  function handleRefreshAnimationEnd() {
    setIsRefreshAnimationActive(false);
  }

  const configMutation = useMutation({
    mutationFn: updateTunnelConfig,
    onSuccess: (config, variables) => {
      setHasSavedToken(config.token_configured);
      if (variables.token !== undefined) setToken("");
      queryClient.setQueryData<TunnelStatus>(TUNNEL_STATUS_QUERY_KEY, (current) =>
        current ? { ...current, config } : current,
      );
    },
  });

  function persistConfig(
    overrides: Partial<Pick<TunnelConfigUpdate, "provider" | "mode" | "hostname">> = {},
  ) {
    const nextHostname =
      overrides.hostname !== undefined
        ? overrides.hostname?.trim() || null
        : hostname.trim() || null;
    configMutation.mutate({
      provider: overrides.provider ?? provider,
      mode: overrides.mode ?? mode,
      hostname: nextHostname,
    });
  }

  function persistToken() {
    const nextToken = token.trim();
    if (!nextToken) return;
    configMutation.mutate({
      provider,
      mode,
      hostname: hostname.trim() || null,
      token: nextToken,
    });
  }

  const mutation = useMutation({
    mutationFn: (action: "start" | "stop") =>
      action === "stop"
        ? stopTunnel()
        : startTunnel({
            provider,
            mode,
            ...(mode === "managed-remote"
              ? {
                  ...(token.trim() ? { token: token.trim() } : {}),
                  hostname: hostname.trim(),
                }
              : {}),
          }),
    onSuccess: () => {
      setToken("");
      void queryClient.invalidateQueries({ queryKey: TUNNEL_STATUS_QUERY_KEY });
    },
  });
  const active = data?.status === "starting" || data?.status === "running";
  const configError = configMutation.error ?? mutation.error;
  const busy = mutation.isPending || configMutation.isPending;
  const isPersistingBeforeStart =
    configMutation.isPending && configMutation.variables?.token === undefined;
  const mutationDetail = axios.isAxiosError(configError)
    ? configError.response?.data?.detail
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

  if (isLoading || (isFetching && !isFetchedAfterMount))
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
        <Button onClick={handleRefresh}>{t("settings.tunnelRefresh")}</Button>
      </Flex>
    );

  const clientName = TUNNEL_CLIENT_NAMES[provider];
  const tunnelErrorMessage =
    data.error_message ?? (data.error ? t(`settings.tunnelError_${data.error}`) : null);
  const canStart =
    data.auth_enabled &&
    data.frontend_available &&
    data.providers[provider] &&
    (mode !== "managed-remote" || ((token.trim() || hasSavedToken) && hostname.trim()));

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
            description={t(isFetching ? "settings.tunnelRefreshing" : "settings.tunnelDescription")}
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
              {
                value: "cloudflare",
                label: "Cloudflare",
                prefix: <TunnelProviderIcon provider="cloudflare" />,
              },
              {
                value: "ngrok",
                label: "Ngrok",
                prefix: <TunnelProviderIcon provider="ngrok" />,
              },
            ]}
            onChange={(value) => {
              const nextProvider = value as TunnelProvider;
              const nextMode: TunnelMode = "quick";
              setProvider(nextProvider);
              setMode(nextMode);
              persistConfig({ provider: nextProvider, mode: nextMode });
            }}
            disabled={active || busy}
            triggerAriaLabel={t("settings.tunnelProvider")}
            triggerStyle={{ width: 160 }}
          />
        </Flex>
        {!data.providers[provider] && (
          <Flex
            align="center"
            justify="between"
            gap="4"
            className="tunnel-setting-row"
          >
            <TunnelSettingLabel
              label={t("settings.tunnelClient", { binary: clientName })}
              description={t("settings.tunnelMissing", { binary: clientName })}
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
                disabled={busy || isFetching || isRefreshAnimationActive}
                onClick={handleRefresh}
              >
                <RefreshCw
                  size={16}
                  className={isRefreshAnimationActive ? "tunnel-refresh-icon--spinning" : undefined}
                  onAnimationEnd={handleRefreshAnimationEnd}
                />
              </IconButton>
            </Flex>
          </Flex>
        )}
        {provider === "ngrok" && (
          <TunnelInfoCallout>
            <Trans
              i18nKey="settings.tunnelNgrokHelp"
              components={{
                dashboard: (
                  <Link
                    href="https://dashboard.ngrok.com/get-started/your-authtoken"
                    target="_blank"
                    rel="noreferrer"
                  />
                ),
              }}
            />
          </TunnelInfoCallout>
        )}
        {provider === "cloudflare" && (
          <>
            <Flex
              align="center"
              justify="between"
              gap="4"
              className="tunnel-setting-row"
            >
              <TunnelSettingLabel label={t("settings.tunnelMode")} />
              <LabeledSelect
                value={mode}
                options={[
                  { value: "quick", label: t("settings.tunnelQuick") },
                  { value: "managed-remote", label: t("settings.tunnelManaged") },
                ]}
                onChange={(value) => {
                  const nextMode = value as TunnelMode;
                  setMode(nextMode);
                  persistConfig({ mode: nextMode });
                }}
                disabled={active || busy}
                triggerAriaLabel={t("settings.tunnelMode")}
                triggerStyle={{ width: 160 }}
              />
            </Flex>
            <TunnelInfoCallout>
              {mode === "quick" ? (
                t("settings.tunnelQuickHelp")
              ) : (
                <Trans
                  i18nKey="settings.tunnelManagedHelp"
                  components={{
                    strong: <strong />,
                    createTunnel: (
                      <Link
                        href="https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/"
                        target="_blank"
                        rel="noreferrer"
                      />
                    ),
                  }}
                />
              )}
            </TunnelInfoCallout>
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
                    onBlur={(event) => persistConfig({ hostname: event.target.value })}
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
                    placeholder={hasSavedToken ? t("settings.tunnelTokenSaved") : undefined}
                    disabled={active || busy}
                    onChange={(event) => setToken(event.target.value)}
                    onBlur={persistToken}
                    className="tunnel-setting-field"
                  />
                </Flex>
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
              <IconButton
                variant="ghost"
                color="gray"
                aria-label={t("settings.tunnelQrCode")}
                onClick={() => setIsQrDialogOpen(true)}
              >
                <QrCodeIcon size={16} />
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
        {(data.error || configError) && (
          <Text
            role="alert"
            size="1"
            color="red"
            className="tunnel-error-message"
          >
            {configError ? errorMessage : tunnelErrorMessage}
          </Text>
        )}
        <Box>
          <Button
            disabled={mutation.isPending || isPersistingBeforeStart || (!active && !canStart)}
            color={active ? "red" : undefined}
            onClick={() => mutation.mutate(active ? "stop" : "start")}
          >
            {busy ? <Spinner size={18} /> : null}
            {t(active ? "settings.tunnelStop" : "settings.tunnelStart")}
          </Button>
        </Box>
      </Flex>
      {data.url ? (
        <TunnelQrCodeDialog
          url={data.url}
          open={isQrDialogOpen}
          onOpenChange={setIsQrDialogOpen}
        />
      ) : null}
    </Box>
  );
}
