import type { SetupProgressEvent } from "../../../shared/ipc";

type Mode = "local" | "remote";

interface SetupPageProps {
  mode: Mode;
  remoteUrl: string;
  progress: SetupProgressEvent[];
  isBusy: boolean;
  error: string | null;
  onModeChange: (mode: Mode) => void;
  onRemoteUrlChange: (value: string) => void;
  onSubmit: () => void;
}

export function SetupPage({
  mode,
  remoteUrl,
  progress,
  isBusy,
  error,
  onModeChange,
  onRemoteUrlChange,
  onSubmit,
}: SetupPageProps) {
  return (
    <section className="content-page content-page-centered">
      <section className="setup-card">
        <p className="eyebrow">OpenFic Desktop</p>
        <h1>连接 OpenFic 后端</h1>
        <p className="description">选择本地运行时，或连接已经运行的远程后端服务。</p>

        <div className="mode-grid">
          <button className={mode === "local" ? "mode-card active" : "mode-card"} onClick={() => onModeChange("local")} type="button">
            <strong>本地运行时</strong>
            <span>下载独立 Python，安装 uv 与 openfic 后启动。</span>
          </button>
          <button className={mode === "remote" ? "mode-card active" : "mode-card"} onClick={() => onModeChange("remote")} type="button">
            <strong>远程后端</strong>
            <span>连接已有 OpenFic 服务，不启动本地后端。</span>
          </button>
        </div>

        {mode === "remote" ? (
          <label className="field">
            <span>后端地址</span>
            <input value={remoteUrl} onChange={(event) => onRemoteUrlChange(event.target.value)} placeholder="http://127.0.0.1:8000" />
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

        <button className="primary-button" disabled={isBusy} onClick={onSubmit} type="button">
          {isBusy ? "处理中..." : mode === "local" ? "设置并启动本地后端" : "连接远程后端"}
        </button>
      </section>
    </section>
  );
}
