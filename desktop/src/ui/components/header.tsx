import { useEffect, useState, type CSSProperties, type MouseEvent } from "react";
import { Link2, Link2Off, Minus, Plus, RefreshCw, Square, Star, Trash2, X } from "lucide-react";
import type { DesktopConfig, DesktopInstance } from "../../shared/config";
import type { UpdateState } from "../../shared/ipc";

interface DesktopHeaderProps {
  activeInstanceId: string | null;
  config: DesktopConfig | null;
  disabled: boolean;
  onAddInstance: () => void;
  onSaveConfig: (config: DesktopConfig) => Promise<void>;
  onSwitchInstance: (instanceId: string) => Promise<void>;
  instancePanelOpen: boolean;
  onInstancePanelOpenChange: (open: boolean) => void;
  canCheckForUpdates: boolean;
  updateState: UpdateState;
  onUpdateAction: () => void;
}

type PingState =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "ok"; latencyMs: number }
  | { status: "failed"; message: string };

function getInstanceLabel(instance: DesktopInstance): string {
  if (instance.mode === "local") return "本地";
  return instance.remoteUrl ?? "";
}

function getLatencyText(state: PingState): string {
  if (state.status === "checking") return "…";
  if (state.status === "ok") return `${state.latencyMs}ms`;
  if (state.status === "failed") return "不可用";
  return "-";
}

function sortInstances(instances: DesktopInstance[]): DesktopInstance[] {
  return [...instances].sort((left, right) => Number(Boolean(right.favorite)) - Number(Boolean(left.favorite)));
}

export function DesktopHeader({
  activeInstanceId,
  config,
  disabled,
  onAddInstance,
  onSaveConfig,
  onSwitchInstance,
  instancePanelOpen,
  onInstancePanelOpenChange,
  canCheckForUpdates,
  updateState,
  onUpdateAction,
}: DesktopHeaderProps) {
  const [panelVisible, setPanelVisible] = useState(false);
  const [pingStates, setPingStates] = useState<Record<string, PingState>>({});
  const [switchingId, setSwitchingId] = useState<string | null>(null);
  const instances = sortInstances(config?.instances ?? []);
  const hasUsableRuntime = instances.some((instance) => pingStates[instance.id]?.status === "ok") || Boolean(activeInstanceId);
  const updateProgress = Math.min(Math.max(updateState.progress ?? 0, 0), 1);
  const updateProgressStyle = { "--update-progress": String(updateProgress) } as CSSProperties;
  const isCheckingForUpdate = updateState.status === "checking";
  const isDownloadingUpdate = updateState.status === "downloading";
  const updateIconState = isCheckingForUpdate
    ? "checking"
    : isDownloadingUpdate
      ? "downloading"
      : updateState.status === "available" || updateState.status === "downloaded"
        ? "available"
        : updateState.status === "error"
          ? "error"
          : "idle";
  const updateAriaLabel = isDownloadingUpdate
    ? `正在下载更新，${Math.round(updateProgress * 100)}%`
    : isCheckingForUpdate
      ? "正在检查更新"
      : updateIconState === "available"
        ? "发现更新"
        : updateIconState === "error"
          ? "更新失败，点击重试"
          : "检查更新";

  const refreshPings = () => {
    if (!instances.length) return;
    setPingStates((current) => {
      const next = { ...current };
      for (const instance of instances) next[instance.id] = { status: "checking" };
      return next;
    });

    for (const instance of instances) {
      void window.openficDesktop
        .pingInstance(instance)
        .then((result) => {
          setPingStates((current) => ({ ...current, [instance.id]: { status: "ok", latencyMs: result.latencyMs } }));
        })
        .catch((err) => {
          setPingStates((current) => ({
            ...current,
            [instance.id]: { status: "failed", message: err instanceof Error ? err.message : "连接失败" },
          }));
        });
    }
  };

  useEffect(() => {
    if (instancePanelOpen) refreshPings();
  }, [instancePanelOpen, config?.activeInstanceId, instances.length]);

  useEffect(() => {
    if (instancePanelOpen) {
      setPanelVisible(true);
      return;
    }

    const timeout = window.setTimeout(() => setPanelVisible(false), 160);
    return () => window.clearTimeout(timeout);
  }, [instancePanelOpen]);

  const handleSwitch = async (instanceId: string) => {
    if (instanceId === activeInstanceId || switchingId) return;
    setSwitchingId(instanceId);
    try {
      await onSwitchInstance(instanceId);
      onInstancePanelOpenChange(false);
    } finally {
      setSwitchingId(null);
    }
  };

  const handleAddInstance = () => {
    onInstancePanelOpenChange(false);
    onAddInstance();
  };

  const toggleFavorite = async (event: MouseEvent<HTMLButtonElement>, instance: DesktopInstance) => {
    event.stopPropagation();
    if (!config) return;
    const nextConfig: DesktopConfig = {
      ...config,
      instances: config.instances.map((item) =>
        item.id === instance.id ? { ...item, favorite: !item.favorite } : item,
      ),
    };
    await onSaveConfig(nextConfig);
  };

  const deleteInstance = async (event: MouseEvent<HTMLButtonElement>, instance: DesktopInstance) => {
    event.stopPropagation();
    if (!config || config.instances.length <= 1) return;

    const remainingInstances = config.instances.filter((item) => item.id !== instance.id);
    const nextActiveInstanceId = config.activeInstanceId === instance.id
      ? sortInstances(remainingInstances)[0]?.id ?? null
      : config.activeInstanceId;
    const nextConfig: DesktopConfig = {
      activeInstanceId: nextActiveInstanceId,
      instances: remainingInstances,
    };

    await onSaveConfig(nextConfig);
    if (config.activeInstanceId === instance.id && nextActiveInstanceId) {
      await onSwitchInstance(nextActiveInstanceId);
      onInstancePanelOpenChange(false);
    }
  };

  return (
    <header className="desktop-header">
      <div className="desktop-titlebar-brand">OpenFic</div>
      <div className="desktop-titlebar-actions">
        <button
          className="titlebar-button titlebar-update-button"
          data-update-state={updateIconState}
          aria-label={updateAriaLabel}
          aria-busy={isCheckingForUpdate || isDownloadingUpdate}
          type="button"
          disabled={!canCheckForUpdates}
          onClick={onUpdateAction}
        >
          {isCheckingForUpdate ? <RefreshCw className="titlebar-update-checking" size={15} strokeWidth={2} /> : null}
          {isDownloadingUpdate ? (
            <svg className="titlebar-update-progress" style={updateProgressStyle} viewBox="0 0 20 20" aria-hidden="true">
              <circle className="titlebar-update-progress-track" cx="10" cy="10" r="7" />
              <circle className="titlebar-update-progress-value" cx="10" cy="10" r="7" />
            </svg>
          ) : null}
          {!isCheckingForUpdate && !isDownloadingUpdate ? <RefreshCw size={15} strokeWidth={2} /> : null}
        </button>
        <div className="instance-switcher">
          <button
            className="titlebar-button titlebar-link-button"
            data-connected={hasUsableRuntime}
            aria-label="实例"
            type="button"
            disabled={disabled}
            onClick={() => onInstancePanelOpenChange(!instancePanelOpen)}
          >
            {hasUsableRuntime ? <Link2 size={15} strokeWidth={2} /> : <Link2Off size={15} strokeWidth={2} />}
          </button>
          {panelVisible && !disabled ? (
            <>
              <button
                className="instance-panel-scrim"
                data-state={instancePanelOpen ? "open" : "closed"}
                type="button"
                aria-label="关闭实例面板"
                onClick={() => onInstancePanelOpenChange(false)}
              />
              <div className="instance-panel" data-state={instancePanelOpen ? "open" : "closed"} role="dialog" aria-label="实例">
                <div className="instance-panel-head">
                  <div>
                    <p className="instance-panel-title">切换实例</p>
                  </div>
                  <button className="instance-icon-button" type="button" aria-label="刷新" onClick={refreshPings}>
                    <RefreshCw size={14} strokeWidth={2} />
                    刷新
                  </button>
                </div>
                <div className="instance-list">
                  {instances.map((instance) => {
                    const pingState = pingStates[instance.id] ?? { status: "idle" };
                    const active = instance.id === activeInstanceId;
                    return (
                      <div
                        className="instance-row"
                        key={instance.id}
                        data-active={active}
                      >
                        <span className="instance-dot" data-status={pingState.status} />
                        <button
                          className="instance-main"
                          type="button"
                          disabled={switchingId !== null}
                          onClick={() => void handleSwitch(instance.id)}
                        >
                          <span className="instance-name-line">
                            <span className="instance-label-wrap">
                              <strong title={getInstanceLabel(instance)}>{getInstanceLabel(instance)}</strong>
                              {active ? <span className="instance-current-badge">当前</span> : null}
                            </span>
                            <span>{getLatencyText(pingState)}</span>
                          </span>
                        </button>
                        <span className="instance-row-actions">
                          <button
                            className="instance-action-button"
                            type="button"
                            aria-label={instance.favorite ? "取消收藏" : "收藏"}
                            data-active={Boolean(instance.favorite)}
                            onClick={(event) => void toggleFavorite(event, instance)}
                          >
                            <Star size={15} strokeWidth={2} fill={instance.favorite ? "currentColor" : "none"} />
                          </button>
                          <button
                            className="instance-action-button"
                            type="button"
                            aria-label="删除实例"
                            disabled={instances.length <= 1}
                            onClick={(event) => void deleteInstance(event, instance)}
                          >
                            <Trash2 size={15} strokeWidth={2} />
                          </button>
                        </span>
                      </div>
                    );
                  })}
                </div>
                <button className="instance-add" type="button" onClick={handleAddInstance}>
                  <Plus size={15} strokeWidth={2} />
                  添加实例
                </button>
              </div>
            </>
          ) : null}
        </div>
        <button className="titlebar-button" aria-label="最小化" type="button" onClick={() => void window.openficDesktop.minimizeWindow()}>
          <Minus size={15} strokeWidth={2} />
        </button>
        <button className="titlebar-button" aria-label="最大化" type="button" onClick={() => void window.openficDesktop.toggleMaximizeWindow()}>
          <Square size={14} strokeWidth={2} />
        </button>
        <button className="titlebar-button titlebar-button-close" aria-label="关闭" type="button" onClick={() => void window.openficDesktop.closeWindow()}>
          <X size={16} strokeWidth={2} />
        </button>
      </div>
    </header>
  );
}
