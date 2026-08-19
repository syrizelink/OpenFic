import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronLeft,
  CircleCheck,
  FolderOpen,
  HardDrive,
  HardDriveDownload,
  RefreshCw,
  Server,
  Settings,
  Trash2,
  X,
} from "lucide-react";
import type { InspectLocalRuntimeResult, SetupProgressEvent, SetupStep } from "../../../shared/ipc";
import type { DesktopInstance } from "../../../shared/config";
import { useTranslation } from "react-i18next";
import "./setup.css";

type WizardStep = "mode" | "remote" | "local-directory" | "local-data" | "local-installing" | "local-success";

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

const STEP_TITLE_KEYS: Record<SetupStep, string> = {
  "download-python": "desktop.setup.downloadPython",
  "extract-python": "desktop.setup.extractPython",
  "create-venv": "desktop.setup.createRuntime",
  "install-uv": "desktop.setup.installUv",
  "install-openfic": "desktop.setup.installOpenFic",
};

const STEP_DETAIL_KEYS: Record<SetupStep, string> = {
  "download-python": "desktop.setup.downloadPythonDetail",
  "extract-python": "desktop.setup.extractPythonDetail",
  "create-venv": "desktop.setup.createRuntimeDetail",
  "install-uv": "desktop.setup.installUvDetail",
  "install-openfic": "desktop.setup.installOpenFicDetail",
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
  initialStep?: "mode" | "remote" | "local-directory" | "local-data" | "local-success";
  initialError?: string | null;
  initialInstallDir?: string | null;
  initialRemoteUrl?: string | null;
  instances: DesktopInstance[];
  activeInstanceId: string | null;
  onClearError: () => void;
  onConnectRemote: (url: string) => void;
  onConnectInstance: (instanceId: string) => void;
  onRequestDeleteInstance: (instanceId: string) => void;
  onOpenDataManagementFor: (instanceId: string) => void;
  onStartLocal: (installDir: string, dataDir: string) => void;
}

function getInstanceDetail(
  instance: DesktopInstance,
  remoteAddressNotSet: string,
  runtimeDirectoryNotSet: string,
): string {
  if (instance.mode === "remote") return instance.remoteUrl ?? remoteAddressNotSet;
  return instance.installDir ? getRuntimeDisplayPath(instance.installDir) : runtimeDirectoryNotSet;
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
  instances,
  activeInstanceId,
  onClearError,
  onConnectRemote,
  onConnectInstance,
  onRequestDeleteInstance,
  onOpenDataManagementFor,
  onStartLocal,
}: SetupPageProps) {
  const { t } = useTranslation();
  const [step, setStep] = useState<WizardStep>(initialStep);
  const [remoteUrl, setRemoteUrl] = useState(initialRemoteUrl ?? "http://127.0.0.1:8000");
  const [installDir, setInstallDir] = useState("");
  const [dataDir, setDataDir] = useState("");
  const [runtimeInspection, setRuntimeInspection] = useState<InspectLocalRuntimeResult | null>(null);
  const [runtimeChecking, setRuntimeChecking] = useState(false);
  const [steps, setSteps] = useState<StepState>(INITIAL_STEPS);
  const [installError, setInstallError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      window.openficDesktop.getDefaultInstallDir(),
      window.openficDesktop.getDefaultDataDir(),
      window.openficDesktop.getConfig(),
    ]).then(([defaultDir, defaultDataDir, config]) => {
      if (cancelled) return;
      const localInstance = config?.instances.find((instance) => instance.mode === "local");
      setInstallDir(initialInstallDir ?? localInstance?.installDir ?? defaultDir);
      setDataDir((current) => current || defaultDataDir);
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

  const pickDataDirectory = async () => {
    onClearError();
    const picked = await window.openficDesktop.selectDirectory();
    if (picked) setDataDir(picked);
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
      setInstallError(err instanceof Error ? err.message : t("desktop.setup.installFailed"));
    }
  };

  const goBack = () => {
    if (step === "remote" || step === "local-directory") {
      onClearError();
      setStep("mode");
    } else if (step === "local-data") {
      onClearError();
      setStep("local-directory");
    }
  };

  const selectMode = (nextStep: "remote" | "local-directory") => {
    onClearError();
    setStep(nextStep);
  };

  const canGoBack = step === "remote" || step === "local-directory" || step === "local-data";

  const runtimeIsReady = runtimeInspection?.status === "ready";
  const runtimeNeedsRepair = runtimeInspection?.status === "incomplete";
  const configuredInstance = runtimeInspection?.configuredInstance ?? null;
  const primaryActionLabel = runtimeIsReady && configuredInstance
    ? t("desktop.setup.useExistingInstance")
    : t("desktop.setup.continue");

  const dataStepPrimaryActionLabel = runtimeIsReady
    ? t("desktop.setup.startLocalInstance")
    : runtimeNeedsRepair
      ? t("desktop.setup.repairRuntime")
      : t("desktop.setup.beginInstall");

  return (
    <section className="content-page content-page-centered">
      <section className="setup-card setup-wizard">
        {step !== "local-success" ? (
          <div className="setup-wizard-top">
            {canGoBack ? (
              <button className="setup-back" type="button" onClick={goBack}>
                <ChevronLeft size={16} strokeWidth={2} />
                {t("desktop.common.back")}
              </button>
            ) : null}
            <div className="setup-heading">
              {EYEBROW[step] ? <p className="eyebrow">{EYEBROW[step]}</p> : null}
              <h1>{TITLE_KEYS[step] ? t(TITLE_KEYS[step]) : ""}</h1>
              {DESCRIPTION_KEYS[step] ? (
                <p className="description">{t(DESCRIPTION_KEYS[step])}</p>
              ) : null}
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
            <div className="setup-mode-content">
              <div className="setup-choices">
                <button className="setup-choice" type="button" onClick={() => selectMode("remote")}>
                  <span className="setup-choice-icon">
                    <Server size={20} strokeWidth={2} />
                  </span>
                  <span className="setup-choice-body">
                    <strong>{t("desktop.setup.connectExistingService")}</strong>
                    <span>{t("desktop.setup.connectExistingServiceDescription")}</span>
                  </span>
                  <span className="setup-choice-arrow">
                    {t("desktop.setup.goToConnection")}
                    <ArrowRight size={15} strokeWidth={2} />
                  </span>
                </button>
                <button className="setup-choice" type="button" onClick={() => selectMode("local-directory")}>
                  <span className="setup-choice-icon">
                    <HardDriveDownload size={20} strokeWidth={2} />
                  </span>
                  <span className="setup-choice-body">
                    <strong>{t("desktop.setup.setUpLocalRuntime")}</strong>
                    <span>{t("desktop.setup.setUpLocalRuntimeDescription")}</span>
                  </span>
                  <span className="setup-choice-arrow">
                    {t("desktop.setup.goToSetup")}
                    <ArrowRight size={15} strokeWidth={2} />
                  </span>
                </button>
              </div>
              {instances.length ? (
                <section className="setup-configured-instances" aria-label={t("desktop.setup.configuredInstances")}>
                  <div className="setup-configured-instances-heading">
                    <h2>{t("desktop.setup.configuredInstances")}</h2>
                    <span>{instances.length}</span>
                  </div>
                  <div className="setup-configured-instance-list">
                    {instances.map((instance) => {
                      const isActive = instance.id === activeInstanceId;
                      return (
                        <div
                          className="setup-configured-instance"
                          role="button"
                          tabIndex={0}
                          key={instance.id}
                          data-active={isActive}
                          onClick={() => onConnectInstance(instance.id)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              onConnectInstance(instance.id);
                            }
                          }}
                        >
                          <span className="setup-configured-instance-icon">
                            {instance.mode === "remote" ? (
                              <Server size={16} strokeWidth={2} />
                            ) : (
                              <HardDrive size={16} strokeWidth={2} />
                            )}
                          </span>
                          <span className="setup-configured-instance-copy">
                            <span className="setup-configured-instance-title">
                              {isActive ? (
                                <span className="setup-configured-instance-badge">{t("desktop.setup.currentInstance")}</span>
                              ) : null}
                              <strong>{instance.name}</strong>
                              {instance.mode === "local" ? (
                                <button
                                  className="setup-configured-instance-settings"
                                  type="button"
                                  title={t("desktop.setup.instanceSettings")}
                                  aria-label={t("desktop.setup.instanceSettings")}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    onOpenDataManagementFor(instance.id);
                                  }}
                                >
                                  <Settings size={13} strokeWidth={2} />
                                </button>
                              ) : null}
                              <button
                                className="setup-configured-instance-settings setup-configured-instance-delete"
                                type="button"
                                title={t("desktop.instanceDeletion.title")}
                                aria-label={t("desktop.instanceDeletion.title")}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  onRequestDeleteInstance(instance.id);
                                }}
                                onKeyDown={(event) => {
                                  if (event.key === "Enter" || event.key === " ") {
                                    event.stopPropagation();
                                  }
                                }}
                              >
                                <Trash2 size={13} strokeWidth={2} />
                              </button>
                            </span>
                            <span
                              title={getInstanceDetail(
                                instance,
                                t("desktop.setup.remoteAddressNotSet"),
                                t("desktop.setup.runtimeDirectoryNotSet"),
                              )}
                            >
                              {getInstanceDetail(
                                instance,
                                t("desktop.setup.remoteAddressNotSet"),
                                t("desktop.setup.runtimeDirectoryNotSet"),
                              )}
                            </span>
                          </span>
                          <span className="setup-configured-instance-action">
                            {isActive ? t("desktop.setup.reconnect") : t("desktop.setup.connect")}
                            <ArrowRight size={15} strokeWidth={2} />
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </section>
              ) : null}
            </div>
          ) : null}

          {step === "remote" ? (
            <div className="setup-form">
              <label className="setup-field">
                <span className="setup-field-label">{t("desktop.setup.backendServiceAddress")}</span>
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
                  {t("desktop.setup.connect")}
                </button>
              </div>
            </div>
          ) : null}

          {step === "local-directory" ? (
            <div className="setup-form">
              <div className="setup-field">
                <span className="setup-field-label">{t("desktop.setup.runtimeDirectory")}</span>
                <div className="setup-dir-row">
                  <span className="setup-dir-value" data-empty={!installDir} title={getRuntimeDisplayPath(installDir)}>
                    {getRuntimeDisplayPath(installDir) || t("desktop.setup.readingDefaultDirectory")}
                  </span>
                  <button className="setup-secondary-button" type="button" onClick={() => void pickDirectory()}>
                    <FolderOpen size={15} strokeWidth={2} style={{ verticalAlign: "-2px", marginRight: 6 }} />
                    {t("desktop.setup.selectDirectory")}
                  </button>
                </div>
              </div>

              {runtimeChecking ? (
                <div className="setup-status">
                  <div className="setup-step-spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                  <span className="setup-status-text">{t("desktop.setup.checkingExistingRuntime")}</span>
                </div>
              ) : null}

              {runtimeIsReady && configuredInstance ? (
                <div className="setup-alert setup-alert-success">
                  <Check size={16} strokeWidth={2.5} className="setup-alert-icon" />
                  <span>{t("desktop.setup.configuredRuntimeFound", { name: configuredInstance.name })}</span>
                </div>
              ) : null}

              {runtimeIsReady && !configuredInstance ? (
                <div className="setup-alert setup-alert-success">
                  <Check size={16} strokeWidth={2.5} className="setup-alert-icon" />
                  <span>{t("desktop.setup.runtimeFound")}</span>
                </div>
              ) : null}

              {runtimeNeedsRepair ? (
                <div className="setup-alert setup-alert-warning">
                  <AlertTriangle size={16} strokeWidth={2} className="setup-alert-icon" />
                  <span>{t("desktop.setup.incompleteRuntimeFound", { message: runtimeInspection.message })}</span>
                </div>
              ) : null}

              <div className="setup-actions">
                <button
                  className="primary-button"
                  type="button"
                  disabled={!installDir || runtimeChecking || !runtimeInspection}
                  onClick={() => {
                    if (runtimeIsReady && configuredInstance) {
                      onConnectInstance(configuredInstance.id);
                      return;
                    }
                    setStep("local-data");
                  }}
                >
                  {primaryActionLabel}
                </button>
              </div>
            </div>
          ) : null}

          {step === "local-data" ? (
            <div className="setup-form">
              <div className="setup-field">
                <span className="setup-field-label">{t("desktop.setup.dataDirectory")}</span>
                <div className="setup-dir-row">
                  <span className="setup-dir-value" data-empty={!dataDir} title={dataDir}>
                    {dataDir || t("desktop.setup.readingDefaultDataDirectory")}
                  </span>
                  <button className="setup-secondary-button" type="button" onClick={() => void pickDataDirectory()}>
                    <FolderOpen size={15} strokeWidth={2} style={{ verticalAlign: "-2px", marginRight: 6 }} />
                    {t("desktop.setup.selectDirectory")}
                  </button>
                </div>
              </div>

              <div className="setup-actions">
                <button
                  className="primary-button"
                  type="button"
                  disabled={!dataDir}
                  onClick={() => {
                    if (runtimeIsReady) {
                      onStartLocal(installDir, dataDir);
                      return;
                    }
                    void beginInstall();
                  }}
                >
                  {dataStepPrimaryActionLabel}
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
                        <span className="setup-step-title">{t(STEP_TITLE_KEYS[stepKey])}</span>
                        {(entry.status === "running" || entry.status === "failed") && !showProgress ? (
                          <span className="setup-step-detail">{entry.status === "failed" ? entry.message : t(STEP_DETAIL_KEYS[stepKey])}</span>
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
                              <span>{t(STEP_DETAIL_KEYS[stepKey])}</span>
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
                      {t("desktop.setup.retry")}
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
                <p className="setup-success-title">{t("desktop.setup.installComplete")}</p>
                <p className="setup-success-desc">
                  {t("desktop.setup.runtimeReady")}
                </p>
              </div>
              <div className="setup-actions" style={{ width: "100%", justifyContent: "center" }}>
                <button
                  className="primary-button"
                  type="button"
                  onClick={() => onStartLocal(installDir, dataDir)}
                >
                  {t("desktop.setup.getStarted")}
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
  "local-data": "",
  "local-installing": "",
  "local-success": "",
};

const TITLE_KEYS: Record<WizardStep, string> = {
  mode: "desktop.setup.welcome",
  remote: "desktop.setup.connectExistingService",
  "local-directory": "desktop.setup.selectInstallDirectory",
  "local-data": "desktop.setup.selectDataDirectory",
  "local-installing": "desktop.setup.installingRuntime",
  "local-success": "",
};

const DESCRIPTION_KEYS: Record<WizardStep, string> = {
  mode: "",
  remote: "",
  "local-directory": "",
  "local-data": "desktop.setup.dataDirectoryDescription",
  "local-installing": "desktop.setup.keepWindowOpen",
  "local-success": "",
};
