import { StartupProgress } from "../../components/startup-progress";
import type { StartupProgressEvent } from "../../../shared/ipc";

interface BootPageProps {
  error: string | null;
  progress: StartupProgressEvent | null;
  onCancel: () => void;
}

export function BootPage({ error, progress, onCancel }: BootPageProps) {
  return (
    <section className="content-page content-page-centered startup-page">
      <div className="boot-state">
        <StartupProgress bare progress={progress} />
        {error ? <p className="error">{error}</p> : null}
        <div className="boot-actions">
          <button className="boot-cancel-button" type="button" onClick={onCancel}>
            取消连接
          </button>
        </div>
      </div>
    </section>
  );
}
