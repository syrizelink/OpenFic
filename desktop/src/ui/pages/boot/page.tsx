import { StartupProgress } from "../../components/startup-progress";
import type { StartupProgressEvent } from "../../../shared/ipc";
import { useTranslation } from "react-i18next";

interface BootPageProps {
  error: string | null;
  progress: StartupProgressEvent | null;
  maintenanceWarning: string | null;
  onCancel: () => void;
  onAcknowledgeMaintenance: () => void;
}

export function BootPage({ error, progress, maintenanceWarning, onCancel, onAcknowledgeMaintenance }: BootPageProps) {
  const { t } = useTranslation();
  return (
    <section className="content-page content-page-centered startup-page">
      <div className="boot-state">
        <StartupProgress bare progress={progress} />
        {error ? <p className="error">{error}</p> : null}
        {maintenanceWarning ? (
          <div className="boot-warning">
            <p className="boot-warning-text">{maintenanceWarning}</p>
            <button className="boot-confirm-button" type="button" onClick={onAcknowledgeMaintenance}>
              {t("desktop.boot.acknowledgeMaintenance")}
            </button>
          </div>
        ) : null}
        {!maintenanceWarning && !error ? (
          <div className="boot-actions">
            <button className="boot-cancel-button" type="button" onClick={onCancel}>
              {t("desktop.boot.cancelConnection")}
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );
}