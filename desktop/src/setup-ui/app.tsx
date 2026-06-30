import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Minus, Settings, Square, X } from "lucide-react";
import type { DesktopConfig } from "../shared/config";
import type { SetupProgressEvent } from "../shared/ipc";

type Mode = "local" | "remote";
type ShellState = "booting" | "setup" | "frontend";
type Appearance = "light" | "dark";

interface DesktopAppearancePayload {
  appearance?: Appearance;
  fontFamily?: string;
  codeFontFamily?: string;
}

interface ShellAppearance {
  appearance: Appearance;
  fontFamily?: string;
  codeFontFamily?: string;
}

interface WebviewIpcMessageEvent extends Event {
  channel: string;
  args: unknown[];
}

function isDesktopAppearancePayload(value: unknown): value is DesktopAppearancePayload {
  if (!value || typeof value !== "object") return false;
  const candidate = value as DesktopAppearancePayload;
  return (
    (candidate.appearance === undefined || candidate.appearance === "light" || candidate.appearance === "dark") &&
    (candidate.fontFamily === undefined || typeof candidate.fontFamily === "string") &&
    (candidate.codeFontFamily === undefined || typeof candidate.codeFontFamily === "string")
  );
}

export function SetupApp() {
  const [mode, setMode] = useState<Mode>("local");
  const [remoteUrl, setRemoteUrl] = useState("http://127.0.0.1:8000");
  const [progress, setProgress] = useState<SetupProgressEvent[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shellState, setShellState] = useState<ShellState>("booting");
  const [webviewKey, setWebviewKey] = useState(0);
  const [shellAppearance, setShellAppearance] = useState<ShellAppearance>({ appearance: "light" });
  const frontendWebviewRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const dispose = window.openficDesktop.onSetupProgress((event) => {
      setProgress((items) => [...items, event]);
    });
    return dispose;
  }, []);

  useEffect(() => {
    let cancelled = false;

    const initialize = async () => {
      try {
        const result = await window.openficDesktop.initializeApp();
        if (cancelled) return;
        setError(result.message ?? null);
        setShellState(result.status === "ready" ? "frontend" : "setup");
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "初始化失败");
        setShellState("setup");
      }
    };

    void initialize();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const handleShowSetup = () => {
      setProgress([]);
      setError(null);
      setIsBusy(false);
      setShellState("setup");
    };

    window.addEventListener("openfic:show-setup", handleShowSetup);
    return () => window.removeEventListener("openfic:show-setup", handleShowSetup);
  }, []);

  useEffect(() => {
    const webview = frontendWebviewRef.current;
    if (!webview) return;

    const handleIpcMessage = (event: Event) => {
      const { channel, args } = event as WebviewIpcMessageEvent;
      if (channel !== "openfic:appearance") return;
      const payload = args[0];
      if (!isDesktopAppearancePayload(payload)) return;

      setShellAppearance((current) => ({
        appearance: payload.appearance ?? current.appearance,
        fontFamily: payload.fontFamily ?? current.fontFamily,
        codeFontFamily: payload.codeFontFamily ?? current.codeFontFamily,
      }));
    };

    webview.addEventListener("ipc-message", handleIpcMessage);
    return () => webview.removeEventListener("ipc-message", handleIpcMessage);
  }, [webviewKey]);

  const showFrontend = () => {
    setProgress([]);
    setError(null);
    setWebviewKey((key) => key + 1);
    setShellState("frontend");
  };

  const handleShowSetup = () => {
    setProgress([]);
    setError(null);
    setIsBusy(false);
    setShellState("setup");
  };

  const handleStartLocal = async () => {
    setIsBusy(true);
    setError(null);
    try {
      await window.openficDesktop.runLocalSetup();
      const config: DesktopConfig = { mode: "local", remoteUrl: null, autoStartLocal: true };
      await window.openficDesktop.saveConfig(config);
      await window.openficDesktop.closeSetup();
      showFrontend();
    } catch (err) {
      setError(err instanceof Error ? err.message : "本地后端设置失败");
    } finally {
      setIsBusy(false);
    }
  };

  const handleUseRemote = async () => {
    setIsBusy(true);
    setError(null);
    try {
      await window.openficDesktop.checkRemote(remoteUrl);
      const config: DesktopConfig = { mode: "remote", remoteUrl, autoStartLocal: false };
      await window.openficDesktop.saveConfig(config);
      await window.openficDesktop.closeSetup();
      showFrontend();
    } catch (err) {
      setError(err instanceof Error ? err.message : "远程后端不可用");
    } finally {
      setIsBusy(false);
    }
  };

  const shellClassName = `desktop-shell radix-themes${shellAppearance.appearance === "dark" ? " dark" : ""}`;
  const shellStyle = {
    ...(shellAppearance.fontFamily
      ? {
          fontFamily: shellAppearance.fontFamily,
          "--app-font-family": shellAppearance.fontFamily,
          "--default-font-family": shellAppearance.fontFamily,
        }
      : {}),
    ...(shellAppearance.codeFontFamily
      ? { "--code-font-family": shellAppearance.codeFontFamily }
      : {}),
  } as CSSProperties;

  return (
    <main className={shellClassName} data-accent-color="gray" data-gray-color="gray" data-radius="medium" data-scaling="100%" style={shellStyle}>
      <header className="desktop-titlebar">
        <div className="desktop-titlebar-brand">OpenFic</div>
        <div className="desktop-titlebar-actions">
          <button className="titlebar-button" aria-label="设置" type="button" onClick={handleShowSetup}>
            <Settings size={15} strokeWidth={2} />
          </button>
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

      <webview
        key={webviewKey}
        ref={frontendWebviewRef}
        className={shellState === "frontend" ? "frontend-webview" : "frontend-webview frontend-webview-hidden"}
        src="app://openfic/"
        preload={window.openficDesktop.frontendHostPreloadPath}
      />

      {shellState !== "frontend" ? (
        <section className="setup-shell">
          <section className="setup-card">
            <p className="eyebrow">OpenFic Desktop</p>
            <h1>{shellState === "booting" ? "正在准备 OpenFic" : "连接 OpenFic 后端"}</h1>
            <p className="description">
              {shellState === "booting"
                ? "正在检查现有配置与后端状态。"
                : "选择本地运行时，或连接已经运行的远程后端服务。"}
            </p>

            {shellState === "setup" ? (
              <>
                <div className="mode-grid">
                  <button className={mode === "local" ? "mode-card active" : "mode-card"} onClick={() => setMode("local")} type="button">
                    <strong>本地运行时</strong>
                    <span>下载独立 Python，安装 uv 与 openfic 后启动。</span>
                  </button>
                  <button className={mode === "remote" ? "mode-card active" : "mode-card"} onClick={() => setMode("remote")} type="button">
                    <strong>远程后端</strong>
                    <span>连接已有 OpenFic 服务，不启动本地后端。</span>
                  </button>
                </div>

                {mode === "remote" ? (
                  <label className="field">
                    <span>后端地址</span>
                    <input value={remoteUrl} onChange={(event) => setRemoteUrl(event.target.value)} placeholder="http://127.0.0.1:8000" />
                  </label>
                ) : null}

                {progress.length ? (
                  <ol className="progress-list">
                    {progress.map((item, index) => (
                      <li key={`${item.step}-${index}`}>{item.message}</li>
                    ))}
                  </ol>
                ) : null}

                {error ? <p className="error">{error}</p> : null}

                <button className="primary-button" disabled={isBusy} onClick={mode === "local" ? handleStartLocal : handleUseRemote} type="button">
                  {isBusy ? "处理中..." : mode === "local" ? "设置并启动本地后端" : "连接远程后端"}
                </button>
              </>
            ) : (
              <div className="boot-state">
                <div className="boot-spinner" aria-hidden="true" />
                {error ? <p className="error">{error}</p> : null}
              </div>
            )}
          </section>
        </section>
      ) : null}
    </main>
  );
}
