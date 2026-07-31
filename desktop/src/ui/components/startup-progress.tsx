import type { StartupProgressEvent } from "../../shared/ipc";
import { useTranslation } from "react-i18next";

interface StartupProgressProps {
  progress: StartupProgressEvent | null;
  bare?: boolean;
}

const STARTUP_TITLE_KEYS: Record<StartupProgressEvent["step"], string> = {
  "load-config": "desktop.startup.loadConfigTitle",
  "check-runtime": "desktop.startup.checkRuntimeTitle",
  "update-python": "desktop.startup.updatePythonTitle",
  "update-openfic": "desktop.startup.updateOpenFicTitle",
  "start-backend": "desktop.startup.startBackendTitle",
  "initialize-backend": "desktop.startup.startBackendTitle",
  "initialize-database": "desktop.startup.startBackendTitle",
  "complete-backend-startup": "desktop.startup.startBackendTitle",
  "check-health": "desktop.startup.verifyServiceTitle",
  "connect-remote": "desktop.startup.connectServiceTitle",
  "verify-remote": "desktop.startup.verifyServiceTitle",
  "check-compatibility": "desktop.startup.checkCompatibilityTitle",
  ready: "desktop.startup.serviceReadyTitle",
};

const STARTUP_MESSAGE_KEYS: Record<StartupProgressEvent["step"], string> = {
  "load-config": "desktop.startup.loadConfigMessage",
  "check-runtime": "desktop.startup.checkRuntimeMessage",
  "update-python": "desktop.startup.updatePythonMessage",
  "update-openfic": "desktop.startup.updateOpenFicMessage",
  "start-backend": "desktop.startup.startBackendMessage",
  "initialize-backend": "desktop.startup.startBackendMessage",
  "initialize-database": "desktop.startup.startBackendMessage",
  "complete-backend-startup": "desktop.startup.startBackendMessage",
  "check-health": "desktop.startup.verifyServiceMessage",
  "connect-remote": "desktop.startup.connectServiceMessage",
  "verify-remote": "desktop.startup.verifyServiceMessage",
  "check-compatibility": "desktop.startup.checkCompatibilityMessage",
  ready: "desktop.startup.serviceReadyMessage",
};

export function StartupProgress({ progress, bare = false }: StartupProgressProps) {
  const { t } = useTranslation();
  const value = Math.round((progress?.progress ?? 0) * 100);
  const title = progress ? t(STARTUP_TITLE_KEYS[progress.step]) : t("desktop.startup.preparingApp");
  const message = progress ? t(STARTUP_MESSAGE_KEYS[progress.step]) : t("desktop.startup.initializingService");

  return (
    <section
      className="startup-progress"
      data-bare={bare}
      data-status={progress?.status ?? "running"}
      aria-live="polite"
    >
      <div className="startup-progress-heading">
        <strong>{title}</strong>
        <span>{value}%</span>
      </div>
      <div
        className="startup-progress-track"
        role="progressbar"
        aria-label={title}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
      >
        <span style={{ width: `${value}%` }} />
      </div>
      <p>{message}</p>
    </section>
  );
}
