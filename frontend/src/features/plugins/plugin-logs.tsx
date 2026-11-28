import { Checkbox, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog, SimpleSelect, toast } from "@/components";
import { getSocket } from "@/lib/socket-client";

import { clearPluginLogs, downloadPluginLogs, fetchPluginLogs, pluginError } from "./api";

const periods = ["10", "60", "360", "1440", "all"] as const;
const counts = ["100", "200", "500", "1000", "all"] as const;

export function PluginLogs({ pluginId }: { pluginId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [period, setPeriod] = useState("all");
  const [count, setCount] = useState("100");
  const [tracking, setTracking] = useState(true);
  const [showTime, setShowTime] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const output = useRef<HTMLPreElement>(null);
  const queryKey = ["plugin-logs", pluginId, period, count];
  const { data, error, isPending } = useQuery({
    queryKey,
    queryFn: ({ signal }) =>
      fetchPluginLogs(
        pluginId,
        {
          minutes: period === "all" ? undefined : Number(period),
          limit: count === "all" ? undefined : Number(count),
        },
        signal,
      ),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchInterval: tracking && period !== "all" ? 30_000 : false,
  });

  useEffect(() => {
    if (!tracking) return;
    const socket = getSocket();
    let timeout: number | undefined;
    let disposed = false;
    function refresh() {
      if (disposed || timeout !== undefined) return;
      timeout = window.setTimeout(() => {
        timeout = undefined;
        void queryClient.invalidateQueries({ queryKey: ["plugin-logs", pluginId] });
      }, 150);
    }
    function subscribe() {
      socket.timeout(2000).emit("plugins:watch-logs", true, refresh);
    }
    function handleLogsChanged(event?: { pluginId?: string }) {
      if (event?.pluginId === pluginId) refresh();
    }
    socket.on("plugins:logs-changed", handleLogsChanged);
    socket.on("plugins:resync", refresh);
    socket.on("connect", subscribe);
    if (socket.connected) subscribe();
    else if (!socket.active) socket.connect();
    return () => {
      disposed = true;
      window.clearTimeout(timeout);
      socket.off("plugins:logs-changed", handleLogsChanged);
      socket.off("plugins:resync", refresh);
      socket.off("connect", subscribe);
      if (socket.connected) socket.emit("plugins:watch-logs", false);
    };
  }, [pluginId, queryClient, tracking]);

  useEffect(() => {
    if (tracking && output.current) output.current.scrollTop = output.current.scrollHeight;
  }, [data, showTime, tracking]);

  const download = useMutation({
    mutationFn: () => downloadPluginLogs(pluginId),
    onError: (failure) => toast.error(pluginError(failure)),
  });
  const clear = useMutation({
    mutationFn: () => clearPluginLogs(pluginId),
    onSuccess: async () => {
      const pluginQueries = { queryKey: ["plugin-logs", pluginId] };
      await queryClient.cancelQueries(pluginQueries);
      queryClient.setQueriesData(pluginQueries, []);
      await queryClient.invalidateQueries(pluginQueries);
    },
    onError: (failure) => toast.error(pluginError(failure)),
  });

  return (
    <Flex
      direction="column"
      gap="3"
    >
      <Flex
        align="center"
        wrap="wrap"
        gap="2"
      >
        <SimpleSelect
          value={period}
          onChange={setPeriod}
          size="2"
          triggerAriaLabel={t("plugins.logFilter.period")}
          triggerPrefix={
            <Text
              color="gray"
              aria-hidden="true"
            >
              {t("plugins.logFilter.filterPrefix")}
            </Text>
          }
          options={periods.map((value) => ({
            value,
            label: t(`plugins.logFilter.periods.${value}`),
          }))}
        />
        <SimpleSelect
          value={count}
          onChange={setCount}
          size="2"
          triggerAriaLabel={t("plugins.logFilter.count")}
          triggerPrefix={
            <Text
              color="gray"
              aria-hidden="true"
            >
              {t("plugins.logFilter.countPrefix")}
            </Text>
          }
          options={counts.map((value) => ({
            value,
            label:
              value === "all"
                ? t("plugins.logFilter.allLines")
                : t("plugins.logFilter.lines", { lineCount: value }),
          }))}
        />
        <Text
          as="label"
          size="2"
          className="plugin-log-toggle"
        >
          <Flex
            as="span"
            align="center"
            gap="2"
          >
            <Checkbox
              checked={tracking}
              onCheckedChange={(checked) => setTracking(checked === true)}
            />
            {t("plugins.logFilter.track")}
          </Flex>
        </Text>
        <Text
          as="label"
          size="2"
          className="plugin-log-toggle"
        >
          <Flex
            as="span"
            align="center"
            gap="2"
          >
            <Checkbox
              checked={showTime}
              onCheckedChange={(checked) => setShowTime(checked === true)}
            />
            {t("plugins.logFilter.time")}
          </Flex>
        </Text>
      </Flex>
      {error && (
        <Text
          role="alert"
          size="2"
          color="red"
        >
          {pluginError(error)}
        </Text>
      )}
      <div className="plugin-log-content dark">
        <Flex
          gap="1"
          className="plugin-log-actions"
        >
          <Tooltip content={t("plugins.logFilter.download")}>
            <IconButton
              type="button"
              size="2"
              variant="soft"
              color="gray"
              aria-label={t("plugins.logFilter.download")}
              loading={download.isPending}
              disabled={clear.isPending}
              onClick={() => download.mutate()}
            >
              <Download
                size={14}
                aria-hidden="true"
              />
            </IconButton>
          </Tooltip>
          <Tooltip content={t("plugins.logFilter.clear")}>
            <IconButton
              type="button"
              size="2"
              variant="soft"
              color="gray"
              className="plugin-log-clear"
              aria-label={t("plugins.logFilter.clear")}
              loading={clear.isPending}
              disabled={download.isPending}
              onClick={() => setConfirmClear(true)}
            >
              <Trash2
                size={14}
                aria-hidden="true"
              />
            </IconButton>
          </Tooltip>
        </Flex>
        <pre
          ref={output}
          className="plugin-logs"
          tabIndex={0}
          aria-label={t("plugins.logs")}
          aria-busy={isPending}
        >
          {data?.length
            ? data
                .map(
                  ({ time, level, action, message }) =>
                    `${showTime ? `${time} ` : ""}[${level.toUpperCase()}] ${action}: ${message}`,
                )
                .join("\n")
            : isPending
              ? t("plugins.working")
              : error
                ? null
                : t("plugins.emptyLogs")}
        </pre>
      </div>
      <ConfirmDialog
        open={confirmClear}
        onOpenChange={setConfirmClear}
        onConfirm={() => clear.mutate()}
        title={t("plugins.logFilter.clearTitle")}
        description={t("plugins.logFilter.clearDescription")}
        confirmText={t("plugins.logFilter.clear")}
      />
    </Flex>
  );
}
