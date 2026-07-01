import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronLeft,
  CircleCheck,
  FolderOpen,
  HardDriveDownload,
  RefreshCw,
  Server,
  X,
} from "lucide-react";
import type { DesktopConfig } from "../../../shared/config";
import type { SetupProgressEvent, SetupStep } from "../../../shared/ipc";
import "./setup.css";

type WizardStep = "mode" | "remote" | "local-directory" | "local-installing" | "local-success";

type StepStatus = "pending" | "running" | "done" | "failed";

interface StepEntry {
  status: StepStatus;
  message: string;
  progress?: number;
}

type StepState = Record<SetupStep, StepEntry>;

const STEP_ORDER: SetupStep[] = [
  "download-python",
  "extract-python",
  "create-venv",
  "install-uv",
  "install-openfic",
];

const STEP_TITLE: Record<SetupStep, string> = {
  "download-python": "下载 Python",
  "extract-python": "解压 Python",
  "create-venv": "创建运行环境",
  "install-uv": "安装 uv",
  "install-openfic": "安装 OpenFic",
};

const INITIAL_STEPS: StepState = {
  "download-python": { status: "pending", message: "" },
  "extract-python": { status: "pending", message: "" },
  "create-venv": { status: "pending", message: "" },
  "install-uv": { status: "pending", message: "" },
  "install-openfic": { status: "pending", message: "" },
};

interface SetupPageProps {
  initialStep?: "mode" | "remote";
  onFinished: () => void;
}

function createInstanceId(): string {
  return `instance-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function getRemoteInstanceName(url: string): string {
  try {
    return new URL(url).host || "Remote";
  } catch {
    return url || "Remote";
  }
}

function normalizeRemoteUrl(url: string): string {
  const trimmed = url.trim().replace(/\/+$/, "");
  try {
    const parsed = new URL(trimmed);
    parsed.protocol = parsed.protocol.toLowerCase();
    parsed.hostname = parsed.hostname.toLowerCase();
    parsed.pathname = parsed.pathname.replace(/\/+$/, "");
    return parsed.toString().replace(/\/+$/, "");
  } catch {
    return trimmed;
  }
}

function applyProgress(prev: StepState, event: SetupProgressEvent): StepState {
  const next = { ...prev };
  const idx = STEP_ORDER.indexOf(event.step);
  if (event.status === "running") {
    for (let i = 0; i < idx; i++) {
      const key = STEP_ORDER[i];
      if (next[key].status !== "failed") {
        next[key] = { ...next[key], status: "done" };
      }
    }
    next[event.step] = { status: "running", message: event.message, progress: event.progress };
  } else if (event.status === "done") {
    next[event.step] = { status: "done", message: event.message || next[event.step].message };
  } else {
    next[event.step] = { status: "failed", message: event.message };
  }
  return next;
}

export function SetupPage({ initialStep = "mode", onFinished }: SetupPageProps) {
  const [step, setStep] = useState<WizardStep>(initialStep);
  const [remoteUrl, setRemoteUrl] = useState("http://127.0.0.1:8000");
  const [installDir, setInstallDir] = useState("");
  const [dirCheck, setDirCheck] = useState<{ exists: boolean; empty: boolean } | null>(null);
  const [dirChecking, setDirChecking] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [remoteError, setRemoteError] = useState<string | null>(null);
  const [steps, setSteps] = useState<StepState>(INITIAL_STEPS);
  const [installError, setInstallError] = useState<string | null>(null);
  const [startingBackend, setStartingBackend] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      window.openficDesktop.getDefaultInstallDir(),
      window.openficDesktop.getConfig(),
    ]).then(([defaultDir, config]) => {
      if (cancelled) return;
      const localInstance = config?.instances.find((instance) => instance.mode === "local");
      setInstallDir(localInstance?.installDir ?? defaultDir);
      const activeInstance = config?.instances.find((instance) => instance.id === config.activeInstanceId);
      if (activeInstance?.mode === "remote" && activeInstance.remoteUrl) setRemoteUrl(activeInstance.remoteUrl);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!installDir || step !== "local-directory") return;
    let cancelled = false;
    setDirChecking(true);
    setDirCheck(null);
    void window.openficDesktop
      .checkDirectoryEmpty(installDir)
      .then((result) => {
        if (!cancelled) {
          setDirCheck(result);
          setDirChecking(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDirCheck(null);
          setDirChecking(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [installDir, step]);

  useEffect(() => {
    const dispose = window.openficDesktop.onSetupProgress((event) => {
      setSteps((prev) => applyProgress(prev, event));
    });
    return dispose;
  }, []);

  const pickDirectory = async () => {
    const picked = await window.openficDesktop.selectDirectory();
    if (picked) setInstallDir(picked);
  };

  const beginInstall = async () => {
    setStep("local-installing");
    setSteps(INITIAL_STEPS);
    setInstallError(null);
    try {
      await window.openficDesktop.installRuntime(installDir);
      setStep("local-success");
    } catch (err) {
      setInstallError(err instanceof Error ? err.message : "安装失败");
    }
  };

  const connectRemote = async () => {
    setConnecting(true);
    setRemoteError(null);
    try {
      const normalizedRemoteUrl = normalizeRemoteUrl(remoteUrl);
      await window.openficDesktop.checkRemote(normalizedRemoteUrl);
      const previousConfig = await window.openficDesktop.getConfig();
      const existingInstance = previousConfig?.instances.find(
        (item) => item.mode === "remote" && item.remoteUrl && normalizeRemoteUrl(item.remoteUrl) === normalizedRemoteUrl,
      );

      if (existingInstance) {
        const config: DesktopConfig = {
          activeInstanceId: existingInstance.id,
          instances: previousConfig?.instances ?? [existingInstance],
        };
        await window.openficDesktop.saveConfig(config);
        await window.openficDesktop.switchInstance(existingInstance.id);
        onFinished();
        return;
      }

      const instance = {
        id: createInstanceId(),
        name: getRemoteInstanceName(normalizedRemoteUrl),
        mode: "remote" as const,
        remoteUrl: normalizedRemoteUrl,
        autoStartLocal: false,
        installDir: null,
      };
      const config: DesktopConfig = {
        activeInstanceId: instance.id,
        instances: [...(previousConfig?.instances ?? []), instance],
      };
      await window.openficDesktop.saveConfig(config);
      await window.openficDesktop.switchInstance(instance.id);
      onFinished();
    } catch (err) {
      setRemoteError(err instanceof Error ? err.message : "无法连接到该地址");
    } finally {
      setConnecting(false);
    }
  };

  const startUsing = async () => {
    setStartingBackend(true);
    setStartError(null);
    try {
      await window.openficDesktop.startLocalBackend(installDir);
      const previousConfig = await window.openficDesktop.getConfig();
      const instance = {
        id: createInstanceId(),
        name: "Local",
        mode: "local" as const,
        remoteUrl: null,
        autoStartLocal: true,
        installDir,
      };
      const config: DesktopConfig = {
        activeInstanceId: instance.id,
        instances: [...(previousConfig?.instances ?? []), instance],
      };
      await window.openficDesktop.saveConfig(config);
      await window.openficDesktop.switchInstance(instance.id);
      onFinished();
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "启动后端失败");
    } finally {
      setStartingBackend(false);
    }
  };

  const goBack = () => {
    if (step === "remote" || step === "local-directory") setStep("mode");
  };

  const canGoBack = step === "remote" || step === "local-directory";

  const dirIsClean = dirCheck?.exists === true && dirCheck.empty;
  const dirNeedsCreate = dirCheck?.exists === false;
  const dirIsOccupied = dirCheck?.exists === true && !dirCheck.empty;

  return (
    <section className="content-page content-page-centered">
      <section className="setup-card setup-wizard">
        {step !== "local-success" ? (
          <div className="setup-wizard-top">
            {canGoBack ? (
              <button className="setup-back" type="button" onClick={goBack}>
                <ChevronLeft size={16} strokeWidth={2} />
                返回
              </button>
            ) : null}
            <div className="setup-heading">
              <p className="eyebrow">{EYEBROW[step]}</p>
              <h1>{TITLE[step]}</h1>
              {DESCRIPTION[step] ? <p className="description">{DESCRIPTION[step]}</p> : null}
            </div>
          </div>
        ) : null}

        <div className="setup-step-enter" key={step}>
          {step === "mode" ? (
            <div className="setup-choices">
              <button className="setup-choice" type="button" onClick={() => setStep("remote")}>
                <span className="setup-choice-icon">
                  <Server size={20} strokeWidth={2} />
                </span>
                <span className="setup-choice-body">
                  <strong>连接到已有服务</strong>
                  <span>连接到已有运行中的 OpenFic 后端服务</span>
                </span>
                <span className="setup-choice-arrow">
                  前往连接
                  <ArrowRight size={15} strokeWidth={2} />
                </span>
              </button>
              <button className="setup-choice" type="button" onClick={() => setStep("local-directory")}>
                <span className="setup-choice-icon">
                  <HardDriveDownload size={20} strokeWidth={2} />
                </span>
                <span className="setup-choice-body">
                  <strong>设置本地运行环境</strong>
                  <span>在本地下载、安装并启动 OpenFic 服务</span>
                </span>
                <span className="setup-choice-arrow">
                  前往设置
                  <ArrowRight size={15} strokeWidth={2} />
                </span>
              </button>
            </div>
          ) : null}

          {step === "remote" ? (
            <div className="setup-form">
              <label className="setup-field">
                <span className="setup-field-label">后端服务地址</span>
                <input
                  value={remoteUrl}
                  onChange={(event) => setRemoteUrl(event.target.value)}
                  placeholder="http://127.0.0.1:8000"
                  disabled={connecting}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void connectRemote();
                  }}
                />
                <span className="setup-field-hint">我们将通过健康检查接口确认服务可用。</span>
              </label>

              {connecting ? (
                <div className="setup-status">
                  <div className="setup-step-spinner" style={{ width: 20, height: 20, borderWidth: 3 }} />
                  <span className="setup-status-text">正在连接 {remoteUrl} …</span>
                </div>
              ) : null}

              {remoteError ? (
                <div className="setup-alert setup-alert-error">
                  <AlertTriangle size={16} strokeWidth={2} className="setup-alert-icon" />
                  <span>{remoteError}</span>
                </div>
              ) : null}

              <div className="setup-actions">
                <button
                  className="primary-button"
                  type="button"
                  disabled={connecting || !remoteUrl.trim()}
                  onClick={() => void connectRemote()}
                >
                  {connecting ? "连接中…" : "连接"}
                </button>
              </div>
            </div>
          ) : null}

          {step === "local-directory" ? (
            <div className="setup-form">
              <div className="setup-field">
                <span className="setup-field-label">安装目录</span>
                <div className="setup-dir-row">
                  <span className="setup-dir-value" data-empty={!installDir} title={installDir}>
                    {installDir || "正在读取默认目录…"}
                  </span>
                  <button className="setup-secondary-button" type="button" onClick={() => void pickDirectory()}>
                    <FolderOpen size={15} strokeWidth={2} style={{ verticalAlign: "-2px", marginRight: 6 }} />
                    选择目录
                  </button>
                </div>
                <span className="setup-field-hint">运行环境将安装到该目录下的 runtime 子目录，不会删除已有文件。</span>
              </div>

              {dirChecking ? (
                <div className="setup-status">
                  <div className="setup-step-spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                  <span className="setup-status-text">正在检查目录…</span>
                </div>
              ) : null}

              {dirIsOccupied ? (
                <div className="setup-alert setup-alert-warning">
                  <AlertTriangle size={16} strokeWidth={2} className="setup-alert-icon" />
                  <span>
                    该目录非空。继续安装将在其中创建 runtime 子目录，不会影响已有文件；如需使用空目录，请选择其他目录。
                  </span>
                </div>
              ) : null}

              {dirNeedsCreate ? (
                <div className="setup-alert setup-alert-success">
                  <Check size={16} strokeWidth={2.5} className="setup-alert-icon" />
                  <span>该目录不存在，安装时将自动创建。</span>
                </div>
              ) : null}

              {dirIsClean ? (
                <div className="setup-alert setup-alert-success">
                  <Check size={16} strokeWidth={2.5} className="setup-alert-icon" />
                  <span>目录为空，可以开始安装。</span>
                </div>
              ) : null}

              <div className="setup-actions">
                <button
                  className="primary-button"
                  type="button"
                  disabled={!installDir || dirChecking || !dirCheck}
                  onClick={() => void beginInstall()}
                >
                  {dirIsOccupied ? "仍然安装" : "开始安装"}
                </button>
              </div>
            </div>
          ) : null}

          {step === "local-installing" ? (
            <div className="setup-form">
              <div className="setup-steps">
                {STEP_ORDER.map((stepKey) => {
                  const entry = steps[stepKey];
                  const isDownload = stepKey === "download-python";
                  const showProgress =
                    isDownload && entry.status === "running" && typeof entry.progress === "number";
                  return (
                    <div
                      className="setup-step"
                      data-done={entry.status === "done"}
                      data-running={entry.status === "running"}
                      data-pending={entry.status === "pending"}
                      data-failed={entry.status === "failed"}
                      key={stepKey}
                    >
                      <div className="setup-step-marker">
                        {entry.status === "done" ? (
                          <Check size={14} strokeWidth={3} />
                        ) : entry.status === "running" ? (
                          <span className="setup-step-spinner" />
                        ) : entry.status === "failed" ? (
                          <X size={14} strokeWidth={3} />
                        ) : null}
                      </div>
                      <div className="setup-step-body">
                        <span className="setup-step-title">{STEP_TITLE[stepKey]}</span>
                        {(entry.status === "running" || entry.status === "failed") && !showProgress ? (
                          <span className="setup-step-detail">{entry.message}</span>
                        ) : null}
                        {showProgress ? (
                          <div className="setup-progress">
                            <div className="setup-progress-track">
                              <div
                                className="setup-progress-fill"
                                style={{ width: `${Math.round((entry.progress ?? 0) * 100)}%` }}
                              />
                            </div>
                            <div className="setup-progress-meta">
                              <span>{entry.message}</span>
                              <span>{Math.round((entry.progress ?? 0) * 100)}%</span>
                            </div>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>

              {installError ? (
                <>
                  <div className="setup-alert setup-alert-error">
                    <AlertTriangle size={16} strokeWidth={2} className="setup-alert-icon" />
                    <span>{installError}</span>
                  </div>
                  <div className="setup-actions">
                    <button className="primary-button" type="button" onClick={() => void beginInstall()}>
                      <RefreshCw size={15} strokeWidth={2} style={{ verticalAlign: "-2px", marginRight: 6 }} />
                      重试
                    </button>
                  </div>
                </>
              ) : null}
            </div>
          ) : null}

          {step === "local-success" ? (
            <div className="setup-success">
              <span className="setup-success-badge">
                <CircleCheck size={34} strokeWidth={2} />
              </span>
              <div>
                <p className="setup-success-title">安装完成</p>
                <p className="setup-success-desc">
                  OpenFic 运行环境已就绪。点击下方按钮启动后端服务并进入 OpenFic。
                </p>
              </div>
              {startError ? (
                <div className="setup-alert setup-alert-error" style={{ textAlign: "left" }}>
                  <AlertTriangle size={16} strokeWidth={2} className="setup-alert-icon" />
                  <span>{startError}</span>
                </div>
              ) : null}
              {startingBackend ? (
                <div className="setup-status">
                  <div className="setup-step-spinner" style={{ width: 20, height: 20, borderWidth: 3 }} />
                  <span className="setup-status-text">正在启动后端服务…</span>
                </div>
              ) : null}
              <div className="setup-actions" style={{ width: "100%", justifyContent: "center" }}>
                <button
                  className="primary-button"
                  type="button"
                  disabled={startingBackend}
                  onClick={() => void startUsing()}
                >
                  {startingBackend ? "启动中…" : "开始使用"}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </section>
  );
}

const EYEBROW: Record<WizardStep, string> = {
  mode: "OpenFic Desktop",
  remote: "连接到已有服务",
  "local-directory": "设置本地运行环境",
  "local-installing": "设置本地运行环境",
  "local-success": "设置本地运行环境",
};

const TITLE: Record<WizardStep, string> = {
  mode: "开始使用 OpenFic",
  remote: "连接到已有服务",
  "local-directory": "选择安装目录",
  "local-installing": "正在安装运行环境",
  "local-success": "",
};

const DESCRIPTION: Record<WizardStep, string> = {
  mode: "连接到 OpenFic 服务以继续",
  remote: "输入远程 OpenFic 后端的服务地址，我们将检查服务是否可用。",
  "local-directory": "运行环境将安装到所选目录的 runtime 子目录中。",
  "local-installing": "请保持窗口开启，安装完成后将自动进入下一步。",
  "local-success": "",
};
