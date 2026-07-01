import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { DesktopConfig } from "../shared/config";
import type { SetupProgressEvent } from "../shared/ipc";
import { DesktopHeader } from "./components/header";
import { BootPage } from "./pages/boot/page";
import { FrontendPage } from "./pages/frontend/page";
import { SetupPage } from "./pages/setup/page";

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

export function App() {
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
      <DesktopHeader onShowSetup={handleShowSetup} />
      <section className="desktop-content">
        {shellState === "booting" ? <BootPage error={error} /> : null}
        {shellState === "setup" ? (
          <SetupPage
            mode={mode}
            remoteUrl={remoteUrl}
            progress={progress}
            isBusy={isBusy}
            error={error}
            onModeChange={setMode}
            onRemoteUrlChange={setRemoteUrl}
            onSubmit={mode === "local" ? handleStartLocal : handleUseRemote}
          />
        ) : null}
        {shellState === "frontend" ? <FrontendPage webviewKey={webviewKey} webviewRef={frontendWebviewRef} /> : null}
      </section>
    </main>
  );
}
