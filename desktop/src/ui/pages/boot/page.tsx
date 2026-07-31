import { StartupProgress } from "../../components/startup-progress";
import type { StartupProgressEvent } from "../../../shared/ipc";
import { useTranslation } from "react-i18next";

interface BootPageProps {
  error: string | null;
  progress: StartupProgressEvent | null;
  onCancel: () => void;
}

export function BootPage({ error, progress, onCancel }: BootPageProps) {
  const { t } = useTranslation();
  return (
    <section className="content-page content-page-centered startup-page">
      <div className="boot-state">
        <StartupProgress bare progress={progress} />
        {error ? <p className="error">{error}</p> : null}
        <div className="boot-actions">
          <button className="boot-cancel-button" type="button" onClick={onCancel}>
            {t("desktop.boot.cancelConnection")}
          </button>
        </div>
      </div>
    </section>
  );
}
