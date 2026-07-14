import type { StartupProgressEvent } from "../../shared/ipc";

interface StartupProgressProps {
  progress: StartupProgressEvent | null;
  bare?: boolean;
}

export function StartupProgress({ progress, bare = false }: StartupProgressProps) {
  const value = Math.round((progress?.progress ?? 0) * 100);
  const title = progress?.title ?? "正在准备 OpenFic";
  const message = progress?.message ?? "正在初始化启动服务";

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
