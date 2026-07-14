import { StartupProgress } from "../../components/startup-progress";
import type { StartupProgressEvent } from "../../../shared/ipc";

interface BootPageProps {
  error: string | null;
  progress: StartupProgressEvent | null;
}

export function BootPage({ error, progress }: BootPageProps) {
  return (
    <section className="content-page content-page-centered startup-page">
      <div className="boot-state">
        <StartupProgress bare progress={progress} />
        {error ? <p className="error">{error}</p> : null}
      </div>
    </section>
  );
}
