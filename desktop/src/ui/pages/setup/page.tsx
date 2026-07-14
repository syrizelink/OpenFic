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
import type { InspectLocalRuntimeResult, SetupProgressEvent, SetupStep } from "../../../shared/ipc";
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

function getRuntimeDisplayPath(installDir: string): string {
  if (!installDir) return "";
  const separator = installDir.includes("\\") ? "\\" : "/";
  return `${installDir.replace(/[\\/]+$/, "")}${separator}runtime`;
}

interface SetupPageProps {
  initialStep?: "mode" | "remote" | "local-directory" | "local-success";
  initialError?: string | null;
  initialInstallDir?: string | null;
  initialRemoteUrl?: string | null;
  onClearError: () => void;
  onConnectRemote: (url: string) => void;
  onStartLocal: (installDir: string) => void;
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

export function SetupPage({
  initialStep = "mode",
  initialError,
  initialInstallDir,
  initialRemoteUrl,
  onClearError,
  onConnectRemote,
  onStartLocal,
}: SetupPageProps) {
  const [step, setStep] = useState<WizardStep>(initialStep);
  const [remoteUrl, setRemoteUrl] = useState(initialRemoteUrl ?? "http://127.0.0.1:8000");
  const [installDir, setInstallDir] = useState("");
  const [runtimeInspection, setRuntimeInspection] = useState<InspectLocalRuntimeResult | null>(null);
  const [runtimeChecking, setRuntimeChecking] = useState(false);
  const [steps, setSteps] = useState<StepState>(INITIAL_STEPS);
  const [installError, setInstallError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      window.openficDesktop.getDefaultInstallDir(),
      window.openficDesktop.getConfig(),
    ]).then(([defaultDir, config]) => {
      if (cancelled) return;
      const localInstance = config?.instances.find((instance) => instance.mode === "local");
      setInstallDir(initialInstallDir ?? localInstance?.installDir ?? defaultDir);
      const activeInstance = config?.instances.find((instance) => instance.id === config.activeInstanceId);
      if (!initialRemoteUrl && activeInstance?.mode === "remote" && activeInstance.remoteUrl) {
        setRemoteUrl(activeInstance.remoteUrl);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [initialInstallDir, initialRemoteUrl]);

  useEffect(() => {
    if (!installDir || step !== "local-directory") return;
    let cancelled = false;
    setRuntimeChecking(true);
    setRuntimeInspection(null);
    void window.openficDesktop
      .inspectLocalRuntime(installDir)
      .then((result) => {
        if (!cancelled) {
          setRuntimeInspection(result);
          setRuntimeChecking(false);
        }
      })
      .catch(() => {
        if (!cancelled) setRuntimeChecking(false);
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
    onClearError();
    const picked = await window.openficDesktop.selectDirectory();
    if (picked) setInstallDir(picked);
  };

  const beginInstall = async () => {
    onClearError();
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

  const goBack = () => {
    if (step === "remote" || step === "local-directory") {
      onClearError();
      setStep("mode");
    }
  };

  const selectMode = (nextStep: "remote" | "local-directory") => {
    onClearError();
    setStep(nextStep);
  };

  const canGoBack = step === "remote" || step === "local-directory";

  const runtimeIsReady = runtimeInspection?.status === "ready";
  const runtimeNeedsRepair = runtimeInspection?.status === "incomplete";
  const configuredInstance = runtimeInspection?.configuredInstance ?? null;
  const primaryActionLabel = runtimeIsReady
    ? configuredInstance
      ? "使用已有实例"
      : "使用已有运行环境"
    : runtimeNeedsRepair
      ? "修复运行环境"
      : "开始安装";

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
              {EYEBROW[step] ? <p className="eyebrow">{EYEBROW[step]}</p> : null}
              <h1>{TITLE[step]}</h1>
              {DESCRIPTION[step] ? <p className="description">{DESCRIPTION[step]}</p> : null}
            </div>
          </div>
        ) : null}

        <div className="setup-step-enter" key={step}>
          {initialError ? (
            <div className="setup-startup-error">
              <div className="setup-alert setup-alert-error">
                <AlertTriangle size={16} strokeWidth={2} className="setup-alert-icon" />
                <span>{initialError}</span>
              </div>
            </div>
          ) : null}
          {step === "mode" ? (
            <div className="setup-choices">
              <button className="setup-choice" type="button" onClick={() => selectMode("remote")}>
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
              <button className="setup-choice" type="button" onClick={() => selectMode("local-directory")}>
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
                  onChange={(event) => {
                    onClearError();
                    setRemoteUrl(event.target.value);
                  }}
                  placeholder="http://127.0.0.1:8000"
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && remoteUrl.trim()) onConnectRemote(remoteUrl);
                  }}
                />
              </label>

              <div className="setup-actions">
                <button
                  className="primary-button"
                  type="button"
                  disabled={!remoteUrl.trim()}
                  onClick={() => onConnectRemote(remoteUrl)}
                >
                  连接
                </button>
              </div>
            </div>
          ) : null}

          {step === "local-directory" ? (
            <div className="setup-form">
              <div className="setup-field">
                <span className="setup-field-label">运行环境目录</span>
                <div className="setup-dir-row">
                  <span className="setup-dir-value" data-empty={!installDir} title={getRuntimeDisplayPath(installDir)}>
                    {getRuntimeDisplayPath(installDir) || "正在读取默认目录…"}
                  </span>
                  <button className="setup-secondary-button" type="button" onClick={() => void pickDirectory()}>
                    <FolderOpen size={15} strokeWidth={2} style={{ verticalAlign: "-2px", marginRight: 6 }} />
                    选择目录
                  </button>
                </div>
              </div>

              {runtimeChecking ? (
                <div className="setup-status">
                  <div className="setup-step-spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                  <span className="setup-status-text">正在检查已有运行环境…</span>
                </div>
              ) : null}

              {runtimeIsReady && configuredInstance ? (
                <div className="setup-alert setup-alert-success">
                  <Check size={16} strokeWidth={2.5} className="setup-alert-icon" />
                  <span>此目录已有已配置且完整的本地实例“{configuredInstance.name}”，将直接启动该实例。</span>
                </div>
              ) : null}

              {runtimeIsReady && !configuredInstance ? (
                <div className="setup-alert setup-alert-success">
                  <Check size={16} strokeWidth={2.5} className="setup-alert-icon" />
                  <span>检测到完整的本地运行环境，启动后将添加为本地实例。</span>
                </div>
              ) : null}

              {runtimeNeedsRepair ? (
                <div className="setup-alert setup-alert-warning">
                  <AlertTriangle size={16} strokeWidth={2} className="setup-alert-icon" />
                  <span>检测到不完整的本地运行环境：{runtimeInspection.message}。继续将修复缺失或损坏的组件。</span>
                </div>
              ) : null}

              <div className="setup-actions">
                <button
                  className="primary-button"
                  type="button"
                  disabled={!installDir || runtimeChecking || !runtimeInspection}
                  onClick={() => {
                    if (runtimeIsReady) {
                      onStartLocal(installDir);
                      return;
                    }
                    void beginInstall();
                  }}
                >
                  {primaryActionLabel}
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
                  OpenFic 运行环境已就绪，开始体验吧
                </p>
              </div>
              <div className="setup-actions" style={{ width: "100%", justifyContent: "center" }}>
                <button
                  className="primary-button"
                  type="button"
                  onClick={() => onStartLocal(installDir)}
                >
                  开始使用
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
  mode: "",
  remote: "",
  "local-directory": "",
  "local-installing": "",
  "local-success": "",
};

const TITLE: Record<WizardStep, string> = {
  mode: "开始使用 OpenFic",
  remote: "连接到已有服务",
  "local-directory": "选择安装目录",
  "local-installing": "正在安装运行环境",
  "local-success": "",
};

const DESCRIPTION: Record<WizardStep, string> = {
  mode: "",
  remote: "",
  "local-directory": "",
  "local-installing": "请保持窗口开启，安装完成后将自动进入下一步。",
  "local-success": "",
};
