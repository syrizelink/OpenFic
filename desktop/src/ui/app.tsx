import { useEffect, useRef, useState, type CSSProperties } from "react";
import { DesktopHeader } from "./components/header";
import { BootPage } from "./pages/boot/page";
import { FrontendPage } from "./pages/frontend/page";
import { SetupPage } from "./pages/setup/page";
import type { DesktopConfig } from "../shared/config";

type ShellState = "booting" | "setup" | "frontend";
type Appearance = "light" | "dark";
type SetupInitialStep = "mode" | "remote";

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
  const [config, setConfig] = useState<DesktopConfig | null>(null);
  const [activeInstanceId, setActiveInstanceId] = useState<string | null>(null);
  const [setupInitialStep, setSetupInitialStep] = useState<SetupInitialStep>("mode");
  const [frontendReadyPartition, setFrontendReadyPartition] = useState<string | null>(null);
  const [shellAppearance, setShellAppearance] = useState<ShellAppearance>({ appearance: "light" });
  const frontendWebviewRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    const initialize = async () => {
      try {
        const result = await window.openficDesktop.initializeApp();
        const nextConfig = await window.openficDesktop.getConfig();
        if (cancelled) return;
        setConfig(nextConfig);
        setActiveInstanceId(result.activeInstanceId ?? nextConfig?.activeInstanceId ?? null);
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

  const refreshConfig = async () => {
    const nextConfig = await window.openficDesktop.getConfig();
    setConfig(nextConfig);
    setActiveInstanceId(nextConfig?.activeInstanceId ?? null);
    return nextConfig;
  };

  const showFrontend = async () => {
    const nextConfig = await refreshConfig();
    setError(null);
    setWebviewKey((key) => key + 1);
    setActiveInstanceId(nextConfig?.activeInstanceId ?? null);
    setShellState("frontend");
  };

  const handleShowSetup = (target: SetupInitialStep = "mode") => {
    setError(null);
    setSetupInitialStep(target);
    setShellState("setup");
  };

  const handleAddInstance = () => {
    const hasLocalInstance = config?.instances.some((instance) => instance.mode === "local") ?? false;
    handleShowSetup(hasLocalInstance ? "remote" : "mode");
  };

  const handleSwitchInstance = async (instanceId: string) => {
    setError(null);
    const result = await window.openficDesktop.switchInstance(instanceId);
    const nextConfig = await refreshConfig();
    setActiveInstanceId(result.activeInstanceId ?? nextConfig?.activeInstanceId ?? instanceId);
    setWebviewKey((key) => key + 1);
    setShellState(result.status === "ready" ? "frontend" : "setup");
  };

  const handleSaveConfig = async (nextConfig: DesktopConfig) => {
    await window.openficDesktop.saveConfig(nextConfig);
    setConfig(nextConfig);
    setActiveInstanceId(nextConfig.activeInstanceId);
  };

  const frontendPartition = activeInstanceId ? `persist:openfic-${activeInstanceId}` : "persist:openfic";

  useEffect(() => {
    if (shellState !== "frontend") return;
    let cancelled = false;
    setFrontendReadyPartition(null);
    void window.openficDesktop.ensureInstanceSession(frontendPartition).then(() => {
      if (!cancelled) setFrontendReadyPartition(frontendPartition);
    });
    return () => {
      cancelled = true;
    };
  }, [frontendPartition, shellState]);

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
      <DesktopHeader
        activeInstanceId={activeInstanceId}
        config={config}
        disabled={shellState === "setup"}
        onAddInstance={handleAddInstance}
        onSaveConfig={handleSaveConfig}
        onSwitchInstance={handleSwitchInstance}
      />
      <section className="desktop-content">
        {shellState === "booting" ? <BootPage error={error} /> : null}
        {shellState === "setup" ? <SetupPage onFinished={() => void showFrontend()} initialStep={setupInitialStep} /> : null}
        {shellState === "frontend" && frontendReadyPartition ? (
          <FrontendPage webviewKey={webviewKey} partition={frontendReadyPartition} webviewRef={frontendWebviewRef} />
        ) : null}
      </section>
    </main>
  );
}
