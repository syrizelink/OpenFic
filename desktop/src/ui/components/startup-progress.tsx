import type { StartupProgressEvent } from "../../shared/ipc";
import { useTranslation } from "react-i18next";

function formatReduced(value: number): string {
  return value.toFixed(1);
}

function renderMaintenanceDetail(
  message: string,
  ...details: Array<string | null>
): string {
  const parts = [message, ...details.filter((detail): detail is string => detail !== null)];
  return parts.join(" · ");
}

interface StartupProgressProps {
  progress: StartupProgressEvent | null;
  bare?: boolean;
}

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
  "maintain-database": "desktop.startup.databaseMaintenanceMessage",
  "connect-remote": "desktop.startup.connectServiceMessage",
  "verify-remote": "desktop.startup.verifyServiceMessage",
  "check-compatibility": "desktop.startup.checkCompatibilityMessage",
  ready: "desktop.startup.serviceReadyMessage",
};

const MAINTENANCE_MESSAGE_KEYS: Record<NonNullable<StartupProgressEvent["maintenancePhase"]>, string> = {
  pending: "desktop.startup.databaseMaintenanceMessage",
  pruning: "desktop.startup.databasePruningMessage",
  migrating: "desktop.startup.databaseMigrationMessage",
  vacuuming: "desktop.startup.databaseVacuumMessage",
  cleanup: "desktop.startup.databaseCleanupMessage",
  ready: "desktop.startup.serviceReadyMessage",
  failed: "desktop.startup.databaseMaintenanceFailedMessage",
};

export function StartupProgress({ progress, bare = false }: StartupProgressProps) {
  const { t } = useTranslation();
  const indeterminate = progress?.indeterminate ?? false;
  const value = Math.round((progress?.progress ?? 0) * 100);
  const title = progress ? t("desktop.startup.startBackendTitle") : t("desktop.startup.preparingApp");
  const message = progress
    ? progress.maintenancePhase
      ? t(MAINTENANCE_MESSAGE_KEYS[progress.maintenancePhase])
      : t(STARTUP_MESSAGE_KEYS[progress.step])
    : t("desktop.startup.initializingService");
  const maintenanceDetail =
    progress?.maintenanceProgress != null
      ? `${Math.round(Math.min(1, Math.max(0, progress.maintenanceProgress)) * 100)}%`
      : null;
  const sizeDetail =
    progress?.maintenanceReclaimedBytes != null &&
    progress?.maintenanceTotalBytes != null &&
    progress.maintenanceTotalBytes > 0
      ? `${formatReduced(progress.maintenanceReclaimedBytes / (1024 ** 3))}/${formatReduced(
          progress.maintenanceTotalBytes / 1024 ** 3,
        )}GB`
      : null;
  const vmOpsDetail =
    progress?.maintenanceVmOps != null
      ? `${progress.maintenanceVmOps.toLocaleString()} VM ops`
      : null;
  const elapsedDetail =
    progress?.maintenanceElapsedSeconds != null
      ? `${formatReduced(progress.maintenanceElapsedSeconds)}s`
      : null;
  const slowHint =
    progress?.maintenancePhase === "migrating" || progress?.maintenancePhase === "vacuuming"
      ? t("desktop.startup.databaseMaintenanceSlowHint")
      : null;

  return (
    <section
      className="startup-progress"
      data-bare={bare}
      data-status={progress?.status ?? "running"}
      aria-live="polite"
    >
      <div className="startup-progress-heading">
        <strong>{title}</strong>
        <span>{indeterminate ? "…" : `${value}%`}</span>
      </div>
      <div
        className="startup-progress-track"
        role="progressbar"
        aria-label={title}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={indeterminate ? undefined : value}
        data-indeterminate={indeterminate}
      >
        <span style={{ width: `${value}%` }} />
      </div>
      <p>
        {renderMaintenanceDetail(message, sizeDetail, vmOpsDetail, elapsedDetail, maintenanceDetail, slowHint)}
      </p>
    </section>
  );
}
