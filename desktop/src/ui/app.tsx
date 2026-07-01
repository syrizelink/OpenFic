import { useEffect, useRef, useState, type CSSProperties } from "react";
import { DesktopHeader } from "./components/header";
import { BootPage } from "./pages/boot/page";
import { FrontendPage } from "./pages/frontend/page";
import { SetupPage } from "./pages/setup/page";

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
  const [error, setError] = useState<string | null>(null);
  const [shellState, setShellState] = useState<ShellState>("booting");
  const [webviewKey, setWebviewKey] = useState(0);
  const [shellAppearance, setShellAppearance] = useState<ShellAppearance>({ appearance: "light" });
  const frontendWebviewRef = useRef<HTMLElement | null>(null);

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
      setError(null);
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
    setError(null);
    setWebviewKey((key) => key + 1);
    setShellState("frontend");
  };

  const handleShowSetup = () => {
    setError(null);
    setShellState("setup");
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
    ...(shellAppearance.codeFontFamily ? { "--code-font-family": shellAppearance.codeFontFamily } : {}),
  } as CSSProperties;

  return (
    <main
      className={shellClassName}
      data-accent-color="gray"
      data-gray-color="gray"
      data-radius="medium"
      data-scaling="100%"
      style={shellStyle}
    >
      <DesktopHeader onShowSetup={handleShowSetup} />
      <section className="desktop-content">
        {shellState === "booting" ? <BootPage error={error} /> : null}
        {shellState === "setup" ? <SetupPage onFinished={showFrontend} /> : null}
        {shellState === "frontend" ? <FrontendPage webviewKey={webviewKey} webviewRef={frontendWebviewRef} /> : null}
      </section>
    </main>
  );
}
