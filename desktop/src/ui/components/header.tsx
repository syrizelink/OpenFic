import { useEffect, useEffectEvent, useRef, useState, type CSSProperties, type MouseEvent } from "react";
import { ArrowLeft, ArrowRight, Link2, Link2Off, Minus, Plus, RefreshCw, Square, Star, Trash2, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { DesktopConfig, DesktopInstance } from "../../shared/config";
import type { UpdateState } from "../../shared/ipc";

interface DesktopHeaderProps {
  activeInstanceId: string | null;
  config: DesktopConfig | null;
  disabled: boolean;
  canGoBack: boolean;
  canGoForward: boolean;
  onGoBack: () => void;
  onGoForward: () => void;
  onAddInstance: () => void;
  onOpenSetup: () => void;
  onOpenDataManagement: () => void;
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

type MenuName = "instance" | "window" | "help";

type MenuShortcut =
  | "menu-window"
  | "menu-instance"
  | "menu-help"
  | "minimize-window"
  | "toggle-maximize"
  | "toggle-full-screen"
  | "zoom-in"
  | "zoom-out"
  | "reset-zoom"
  | "close-window"
  | "toggle-dev-tools";

function getMenuShortcut(event: KeyboardEvent): MenuShortcut | null {
  if (event.altKey && !event.ctrlKey && !event.metaKey) {
    if (event.code === "KeyW") return "menu-window";
    if (event.code === "KeyI") return "menu-instance";
    if (event.code === "KeyH") return "menu-help";
  }
  if (event.key === "F11" && !event.ctrlKey && !event.altKey && !event.metaKey) return "toggle-full-screen";
  if (event.key === "F12" && !event.ctrlKey && !event.altKey && !event.metaKey) return "toggle-dev-tools";
  if (!event.ctrlKey || event.altKey || event.metaKey) return null;
  if (event.shiftKey) {
    if (event.code === "KeyM") return "toggle-maximize";
    return null;
  }
  if (event.code === "KeyM") return "minimize-window";
  if (event.code === "Equal" || event.code === "NumpadAdd") return "zoom-in";
  if (event.code === "Minus" || event.code === "NumpadSubtract") return "zoom-out";
  if (event.code === "Digit0" || event.code === "Numpad0") return "reset-zoom";
  if (event.code === "KeyQ") return "close-window";
  return null;
}

function isMenuShortcut(value: unknown): value is MenuShortcut {
  return typeof value === "string" && [
    "menu-window",
    "menu-instance",
    "menu-help",
    "minimize-window",
    "toggle-maximize",
    "toggle-full-screen",
    "zoom-in",
    "zoom-out",
    "reset-zoom",
    "close-window",
    "toggle-dev-tools",
  ].includes(value);
}

function getInstanceLabel(instance: DesktopInstance, local: string): string {
  if (instance.mode === "local") return local;
  return instance.remoteUrl ?? "";
}

function getLatencyText(state: PingState, unavailable: string): string {
  if (state.status === "checking") return "…";
  if (state.status === "ok") return `${state.latencyMs}ms`;
  if (state.status === "failed") return unavailable;
  return "-";
}

function sortInstances(instances: DesktopInstance[]): DesktopInstance[] {
  return [...instances].sort((left, right) => Number(Boolean(right.favorite)) - Number(Boolean(left.favorite)));
}

export function DesktopHeader({
  activeInstanceId,
  config,
  disabled,
  canGoBack,
  canGoForward,
  onGoBack,
  onGoForward,
  onAddInstance,
  onOpenSetup,
  onOpenDataManagement,
  onSaveConfig,
  onSwitchInstance,
  instancePanelOpen,
  onInstancePanelOpenChange,
  canCheckForUpdates,
  updateState,
  onUpdateAction,
}: DesktopHeaderProps) {
  const { t } = useTranslation();
  const [panelVisible, setPanelVisible] = useState(false);
  const [pingStates, setPingStates] = useState<Record<string, PingState>>({});
  const [switchingId, setSwitchingId] = useState<string | null>(null);
  const [isExportingLogs, setIsExportingLogs] = useState(false);
  const [openMenu, setOpenMenu] = useState<MenuName | null>(null);
  const [visibleMenu, setVisibleMenu] = useState<MenuName | null>(null);
  const [zoomFactor, setZoomFactor] = useState(1);
  const menuBarRef = useRef<HTMLDivElement>(null);
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
    ? t("desktop.header.updateDownloading", { progress: Math.round(updateProgress * 100) })
    : isCheckingForUpdate
      ? t("desktop.header.updateChecking")
      : updateIconState === "available"
        ? t("desktop.header.updateAvailable")
        : updateIconState === "error"
          ? t("desktop.header.updateFailedRetry")
          : t("desktop.header.checkForUpdates");

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
            [instance.id]: { status: "failed", message: err instanceof Error ? err.message : t("desktop.header.connectionFailed") },
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

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      if (!menuBarRef.current?.contains(event.target as Node)) setOpenMenu(null);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpenMenu(null);
    };

    document.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  useEffect(() => {
    if (openMenu) {
      setVisibleMenu(openMenu);
      return;
    }

    const timeout = window.setTimeout(() => setVisibleMenu(null), 160);
    return () => window.clearTimeout(timeout);
  }, [openMenu]);

  useEffect(() => {
    void window.openficDesktop.getZoomFactor().then(setZoomFactor);
    return window.openficDesktop.onZoomFactorChanged(setZoomFactor);
  }, []);

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
    setOpenMenu(null);
    onAddInstance();
  };

  const handleOpenSetup = () => {
    onInstancePanelOpenChange(false);
    setOpenMenu(null);
    onOpenSetup();
  };

  const handleOpenDataManagement = () => {
    onInstancePanelOpenChange(false);
    setOpenMenu(null);
    onOpenDataManagement();
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

  const handleExportLogs = async () => {
    setOpenMenu(null);
    if (isExportingLogs) return;
    setIsExportingLogs(true);
    try {
      await window.openficDesktop.exportLogs();
    } catch {
      // The main process presents an actionable error dialog.
    } finally {
      setIsExportingLogs(false);
    }
  };

  const handleChangeZoom = async (zoomChange: "in" | "out" | "reset") => {
    const nextZoomFactor = zoomChange === "reset"
      ? 1.1
      : zoomFactor + (zoomChange === "in" ? 0.1 : -0.1);
    setOpenMenu(null);
    await window.openficDesktop.saveZoomFactor(nextZoomFactor);
  };

  const handleHelpAction = (action: () => Promise<void>) => {
    setOpenMenu(null);
    void action();
  };

  const toggleMenu = (menu: MenuName) => {
    setOpenMenu((current) => (current === menu ? null : menu));
  };

  const handleMenuShortcut = useEffectEvent((shortcut: MenuShortcut) => {
    if (shortcut === "menu-window") {
      setOpenMenu("window");
      return;
    }
    if (shortcut === "menu-instance") {
      setOpenMenu("instance");
      return;
    }
    if (shortcut === "menu-help") {
      setOpenMenu("help");
      return;
    }
    if (shortcut === "minimize-window") {
      setOpenMenu(null);
      void window.openficDesktop.minimizeWindow();
      return;
    }
    if (shortcut === "toggle-maximize") {
      setOpenMenu(null);
      void window.openficDesktop.toggleMaximizeWindow();
      return;
    }
    if (shortcut === "toggle-full-screen") {
      setOpenMenu(null);
      void window.openficDesktop.toggleFullScreen();
      return;
    }
    if (shortcut === "zoom-in") {
      void handleChangeZoom("in");
      return;
    }
    if (shortcut === "zoom-out") {
      void handleChangeZoom("out");
      return;
    }
    if (shortcut === "reset-zoom") {
      void handleChangeZoom("reset");
      return;
    }
    if (shortcut === "close-window") {
      setOpenMenu(null);
      void window.openficDesktop.closeWindow();
      return;
    }
    handleHelpAction(window.openficDesktop.toggleDevTools);
  });

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const shortcut = getMenuShortcut(event);
      if (!shortcut) return;
      event.preventDefault();
      handleMenuShortcut(shortcut);
    };
    const handleWebviewShortcut = (event: Event) => {
      const shortcut = (event as CustomEvent<unknown>).detail;
      if (isMenuShortcut(shortcut)) handleMenuShortcut(shortcut);
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("openfic:menu-shortcut", handleWebviewShortcut);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("openfic:menu-shortcut", handleWebviewShortcut);
    };
  }, []);

  return (
      <header className="desktop-header">
        <div className="desktop-titlebar-left">
          <nav className="desktop-navigation" aria-label={t("desktop.header.navigation")}>
            <button
              className="titlebar-button"
              aria-label={t("desktop.header.goBack")}
              type="button"
              disabled={!canGoBack}
              onClick={onGoBack}
            >
              <ArrowLeft size={15} strokeWidth={2} />
            </button>
            <button
              className="titlebar-button"
              aria-label={t("desktop.header.goForward")}
              type="button"
              disabled={!canGoForward}
              onClick={onGoForward}
            >
              <ArrowRight size={15} strokeWidth={2} />
            </button>
          </nav>
          <nav className="desktop-menu-bar" aria-label={t("desktop.header.appMenu")} ref={menuBarRef}>
          <div className="desktop-menu">
            <button
              className="desktop-menu-trigger"
              type="button"
              aria-expanded={openMenu === "window"}
              aria-haspopup="menu"
              onClick={() => toggleMenu("window")}
            >
              {t("desktop.header.windowMenu")}
            </button>
            {visibleMenu === "window" ? (
              <div
                className="desktop-menu-panel"
                data-state={openMenu === "window" ? "open" : "closed"}
                role="menu"
                aria-label={t("desktop.header.windowMenu")}
              >
                <button className="desktop-menu-item" type="button" role="menuitem" onClick={() => void window.openficDesktop.reloadWindow()}>
                  {t("desktop.header.reload")}
                </button>
                <span className="desktop-menu-separator" role="separator" />
                <button
                  className="desktop-menu-item"
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setOpenMenu(null);
                    void window.openficDesktop.minimizeWindow();
                  }}
                >
                  <span>{t("desktop.header.minimize")}</span>
                  <span className="desktop-menu-item-shortcut">Ctrl+M</span>
                </button>
                <button
                  className="desktop-menu-item"
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setOpenMenu(null);
                    void window.openficDesktop.toggleMaximizeWindow();
                  }}
                >
                  <span>{t("desktop.header.toggleMaximize")}</span>
                  <span className="desktop-menu-item-shortcut">Ctrl+Shift+M</span>
                </button>
                <button
                  className="desktop-menu-item"
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setOpenMenu(null);
                    void window.openficDesktop.toggleFullScreen();
                  }}
                >
                  <span>{t("desktop.header.toggleFullscreen")}</span>
                  <span className="desktop-menu-item-shortcut">F11</span>
                </button>
                <span className="desktop-menu-separator" role="separator" />
                <button className="desktop-menu-item" type="button" role="menuitem" onClick={() => void handleChangeZoom("in")}>
                  <span>{t("desktop.header.zoomIn")}</span>
                  <span className="desktop-menu-item-shortcut">Ctrl++</span>
                </button>
                <button className="desktop-menu-item" type="button" role="menuitem" onClick={() => void handleChangeZoom("out")}>
                  <span>{t("desktop.header.zoomOut")}</span>
                  <span className="desktop-menu-item-shortcut">Ctrl+-</span>
                </button>
                <button className="desktop-menu-item" type="button" role="menuitem" onClick={() => void handleChangeZoom("reset")}>
                  <span>{t("desktop.header.resetZoom")}</span>
                  <span className="desktop-menu-item-shortcut">Ctrl+0</span>
                  <span className="desktop-menu-item-value">{Math.round(zoomFactor * 100)}%</span>
                </button>
                <span className="desktop-menu-separator" role="separator" />
                <button className="desktop-menu-item" type="button" role="menuitem" onClick={() => void window.openficDesktop.closeWindow()}>
                  <span>{t("desktop.header.quitApp")}</span>
                  <span className="desktop-menu-item-shortcut">Ctrl+Q</span>
                </button>
              </div>
            ) : null}
          </div>
          <div className="desktop-menu">
            <button
              className="desktop-menu-trigger"
              type="button"
              aria-expanded={openMenu === "instance"}
              aria-haspopup="menu"
              onClick={() => toggleMenu("instance")}
            >
              {t("desktop.header.instanceMenu")}
            </button>
            {visibleMenu === "instance" ? (
              <div
                className="desktop-menu-panel"
                data-state={openMenu === "instance" ? "open" : "closed"}
                role="menu"
                aria-label={t("desktop.header.instance")}
              >
                <button className="desktop-menu-item" type="button" role="menuitem" disabled={disabled} onClick={handleAddInstance}>
                  {t("desktop.header.addInstance")}
                </button>
                <button className="desktop-menu-item" type="button" role="menuitem" disabled={disabled} onClick={handleOpenSetup}>
                  {t("desktop.header.manageInstances")}
                </button>
                <button
                  className="desktop-menu-item"
                  type="button"
                  role="menuitem"
                  disabled={disabled}
                  onClick={handleOpenDataManagement}
                >
                  {t("desktop.header.dataManagement")}
                </button>
              </div>
            ) : null}
          </div>
          <div className="desktop-menu">
            <button
              className="desktop-menu-trigger"
              type="button"
              aria-expanded={openMenu === "help"}
              aria-haspopup="menu"
              onClick={() => toggleMenu("help")}
            >
              {t("desktop.header.helpMenu")}
            </button>
            {visibleMenu === "help" ? (
              <div
                className="desktop-menu-panel"
                data-state={openMenu === "help" ? "open" : "closed"}
                role="menu"
                aria-label={t("desktop.header.helpMenu")}
              >
                <button className="desktop-menu-item" type="button" role="menuitem" onClick={() => handleHelpAction(window.openficDesktop.openProjectHome)}>
                  {t("desktop.header.projectHome")}
                </button>
                <button className="desktop-menu-item" type="button" role="menuitem" onClick={() => handleHelpAction(window.openficDesktop.reportBug)}>
                  {t("desktop.header.reportBug")}
                </button>
                <button className="desktop-menu-item" type="button" role="menuitem" onClick={() => handleHelpAction(window.openficDesktop.suggestFeature)}>
                  {t("desktop.header.suggestFeature")}
                </button>
                <span className="desktop-menu-separator" role="separator" />
                <button className="desktop-menu-item" type="button" role="menuitem" onClick={() => void handleExportLogs()}>
                  {t("desktop.header.exportDebugLogs")}
                </button>
                <button className="desktop-menu-item" type="button" role="menuitem" onClick={() => handleHelpAction(window.openficDesktop.toggleDevTools)}>
                  <span>{t("desktop.header.toggleDevTools")}</span>
                  <span className="desktop-menu-item-shortcut">F12</span>
                </button>
              </div>
            ) : null}
          </div>
        </nav>
      </div>
      {visibleMenu ? (
        <button
          className="desktop-menu-scrim"
          data-state={openMenu ? "open" : "closed"}
          type="button"
          aria-label={t("desktop.header.closeMenu")}
          onClick={() => setOpenMenu(null)}
        />
      ) : null}
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
            aria-label={t("desktop.header.instance")}
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
                aria-label={t("desktop.header.closeInstancePanel")}
                onClick={() => onInstancePanelOpenChange(false)}
              />
              <div
                className="instance-panel"
                data-state={instancePanelOpen ? "open" : "closed"}
                role="dialog"
                aria-label={t("desktop.header.instance")}
              >
                <div className="instance-panel-head">
                  <div>
                    <p className="instance-panel-title">{t("desktop.header.switchInstance")}</p>
                  </div>
                  <button
                    className="instance-icon-button"
                    type="button"
                    aria-label={t("desktop.header.refresh")}
                    onClick={refreshPings}
                  >
                    <RefreshCw size={14} strokeWidth={2} />
                    {t("desktop.header.refresh")}
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
                              <strong title={getInstanceLabel(instance, t("desktop.header.local"))}>
                                {getInstanceLabel(instance, t("desktop.header.local"))}
                              </strong>
                              {active ? <span className="instance-current-badge">{t("desktop.header.current")}</span> : null}
                            </span>
                            <span>{getLatencyText(pingState, t("desktop.header.unavailable"))}</span>
                          </span>
                        </button>
                        <span className="instance-row-actions">
                          <button
                            className="instance-action-button"
                            type="button"
                            aria-label={
                              instance.favorite ? t("desktop.header.unfavorite") : t("desktop.header.favorite")
                            }
                            data-active={Boolean(instance.favorite)}
                            onClick={(event) => void toggleFavorite(event, instance)}
                          >
                            <Star size={15} strokeWidth={2} fill={instance.favorite ? "currentColor" : "none"} />
                          </button>
                          <button
                            className="instance-action-button"
                            type="button"
                            aria-label={t("desktop.header.deleteInstance")}
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
                  {t("desktop.header.addInstance")}
                </button>
              </div>
            </>
          ) : null}
        </div>
        <button
          className="titlebar-button"
          aria-label={t("desktop.header.minimizeWindow")}
          type="button"
          onClick={() => void window.openficDesktop.minimizeWindow()}
        >
          <Minus size={15} strokeWidth={2} />
        </button>
        <button
          className="titlebar-button"
          aria-label={t("desktop.header.maximizeWindow")}
          type="button"
          onClick={() => void window.openficDesktop.toggleMaximizeWindow()}
        >
          <Square size={14} strokeWidth={2} />
        </button>
        <button
          className="titlebar-button titlebar-button-close"
          aria-label={t("desktop.header.closeWindow")}
          type="button"
          onClick={() => void window.openficDesktop.closeWindow()}
        >
          <X size={16} strokeWidth={2} />
        </button>
      </div>
    </header>
  );
}
