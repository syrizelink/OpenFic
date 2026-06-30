import { useEffect, useState } from "react";
import type { DesktopConfig } from "../shared/config";
import type { SetupProgressEvent } from "../shared/ipc";

type Mode = "local" | "remote";

export function SetupApp() {
  const [mode, setMode] = useState<Mode>("local");
  const [remoteUrl, setRemoteUrl] = useState("http://127.0.0.1:8000");
  const [progress, setProgress] = useState<SetupProgressEvent[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dispose = window.openficDesktop.onSetupProgress((event) => {
      setProgress((items) => [...items, event]);
    });
    return dispose;
  }, []);

  const handleStartLocal = async () => {
    setIsBusy(true);
    setError(null);
    try {
      await window.openficDesktop.runLocalSetup();
      const config: DesktopConfig = { mode: "local", remoteUrl: null, autoStartLocal: true };
      await window.openficDesktop.saveConfig(config);
      await window.openficDesktop.closeSetup();
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "远程后端不可用");
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <main className="setup-shell">
      <section className="setup-card">
        <p className="eyebrow">OpenFic Desktop</p>
        <h1>连接 OpenFic 后端</h1>
        <p className="description">选择本地运行时，或连接已经运行的远程后端服务。</p>

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
      </section>
    </main>
  );
}
