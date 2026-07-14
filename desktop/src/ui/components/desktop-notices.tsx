import { AlertTriangle, Download, RefreshCw, RotateCcw } from "lucide-react";
import type { UpdateState } from "../../shared/ipc";

interface DesktopNoticesProps {
  compatibilityWarning: string | null;
  updateState: UpdateState;
  onCheckForUpdate: () => void;
  onDownloadUpdate: () => void;
  onInstallUpdate: () => void;
}

function formatBytes(bytes: number | undefined): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** unitIndex;
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[unitIndex]}`;
}

export function DesktopNotices({
  compatibilityWarning,
  updateState,
  onCheckForUpdate,
  onDownloadUpdate,
  onInstallUpdate,
}: DesktopNoticesProps) {
  const shouldShowUpdate = ["available", "downloading", "downloaded", "error"].includes(updateState.status);

  if (!compatibilityWarning && !shouldShowUpdate) return null;

  return (
    <aside className="desktop-notices" aria-live="polite">
      {compatibilityWarning ? (
        <section className="desktop-notice desktop-notice-warning" role="status">
          <AlertTriangle size={17} strokeWidth={2} aria-hidden="true" />
          <p>{compatibilityWarning}</p>
        </section>
      ) : null}
      {updateState.status === "available" ? (
        <section className="desktop-notice desktop-notice-update" role="status">
          <div className="desktop-notice-copy">
            <p className="desktop-notice-title">发现 OpenFic {updateState.version}</p>
            <p>新版本已准备就绪，下载后由你决定何时重启安装。</p>
          </div>
          <button className="desktop-notice-primary" type="button" onClick={onDownloadUpdate}>
            <Download size={15} strokeWidth={2} />
            下载更新
          </button>
        </section>
      ) : null}
      {updateState.status === "downloading" ? (
        <section className="desktop-notice desktop-notice-update" role="status">
          <div className="desktop-notice-copy">
            <p className="desktop-notice-title">正在下载更新</p>
            <p>{formatBytes(updateState.transferred)} / {formatBytes(updateState.total)}</p>
          </div>
          <div className="desktop-update-progress" aria-label={`下载进度 ${Math.round((updateState.progress ?? 0) * 100)}%`}>
            <span style={{ width: `${Math.min(Math.max(updateState.progress ?? 0, 0), 1) * 100}%` }} />
          </div>
        </section>
      ) : null}
      {updateState.status === "downloaded" ? (
        <section className="desktop-notice desktop-notice-update" role="status">
          <div className="desktop-notice-copy">
            <p className="desktop-notice-title">OpenFic {updateState.version} 已下载</p>
            <p>重启后将安装更新，本地后端也会同步到新版本。</p>
          </div>
          <button className="desktop-notice-primary" type="button" onClick={onInstallUpdate}>
            <RotateCcw size={15} strokeWidth={2} />
            重启并安装
          </button>
        </section>
      ) : null}
      {updateState.status === "error" ? (
        <section className="desktop-notice desktop-notice-error" role="alert">
          <div className="desktop-notice-copy">
            <p className="desktop-notice-title">检查更新失败</p>
            <p>{updateState.message ?? "更新服务暂时不可用。"}</p>
          </div>
          <button className="desktop-notice-secondary" type="button" onClick={onCheckForUpdate}>
            <RefreshCw size={15} strokeWidth={2} />
            重试
          </button>
        </section>
      ) : null}
    </aside>
  );
}
