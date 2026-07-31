import { useEffect, useState } from "react";
import { AlertTriangle, ChevronRight, Download, ExternalLink, PackageSearch, RefreshCw, RotateCcw, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import { useTranslation } from "react-i18next";
import type { UpdateState } from "../../shared/ipc";

interface DesktopNoticesProps {
  compatibilityWarning: string | null;
  updateDialogOpen: boolean;
  updateState: UpdateState;
  onCheckForUpdate: () => void;
  onDownloadUpdate: () => void;
  onCancelDownload: () => void;
  onInstallUpdate: () => void;
  onOpenRelease: () => void;
  onCloseCompatibilityWarning: () => void;
  onCloseUpdateDialog: () => void;
}

function formatBytes(bytes: number | undefined): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** unitIndex;
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[unitIndex]}`;
}

function getReleaseNotesText(releaseNotes: string | undefined, fallback: string): string {
  return releaseNotes || fallback;
}

function ReleaseNotes({ releaseNotes }: { releaseNotes: string }) {
  return (
    <div className="desktop-release-notes-content">
      <ReactMarkdown
        rehypePlugins={[rehypeRaw, rehypeSanitize]}
        components={{
          a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer">{children}</a>,
        }}
      >
        {releaseNotes}
      </ReactMarkdown>
    </div>
  );
}

export function DesktopNotices({
  compatibilityWarning,
  updateDialogOpen,
  updateState,
  onCheckForUpdate,
  onDownloadUpdate,
  onCancelDownload,
  onInstallUpdate,
  onOpenRelease,
  onCloseCompatibilityWarning,
  onCloseUpdateDialog,
}: DesktopNoticesProps) {
  const { t } = useTranslation();
  const [updatePanelVisible, setUpdatePanelVisible] = useState(false);
  const [releaseNotesOpen, setReleaseNotesOpen] = useState(true);
  const releaseNotes = getReleaseNotesText(updateState.releaseNotes, t("desktop.notices.releaseNotesFallback"));
  const hasVersionDetails = ["available", "downloading", "downloaded"].includes(updateState.status);

  useEffect(() => {
    if (updateDialogOpen) {
      setUpdatePanelVisible(true);
      return;
    }

    const timeout = window.setTimeout(() => setUpdatePanelVisible(false), 160);
    return () => window.clearTimeout(timeout);
  }, [updateDialogOpen]);

  const showUpdatePanel = !compatibilityWarning && updatePanelVisible;
  if (!compatibilityWarning && !showUpdatePanel) return null;

  return (
    <>
      {compatibilityWarning ? (
        <aside className="desktop-notices" aria-live="polite">
          <section className="desktop-notice desktop-notice-warning" role="status">
            <AlertTriangle size={17} strokeWidth={2} aria-hidden="true" />
            <p>{compatibilityWarning}</p>
            <button
              className="desktop-notice-warning-dismiss"
              type="button"
              aria-label={t("desktop.notices.closeCompatibilityWarning")}
              onClick={onCloseCompatibilityWarning}
            >
              <X size={16} strokeWidth={2} />
            </button>
          </section>
        </aside>
      ) : null}
      {showUpdatePanel ? (
        <>
          <button
            className="desktop-update-panel-scrim"
            data-state={updateDialogOpen ? "open" : "closed"}
            type="button"
            aria-label={t("desktop.notices.closeUpdatePanel")}
            onClick={onCloseUpdateDialog}
          />
          <aside className="desktop-notice desktop-notice-update desktop-update-panel" data-state={updateDialogOpen ? "open" : "closed"} role="status" aria-live="polite">
            {!hasVersionDetails ? (
              <button
                className="desktop-notice-dismiss"
                type="button"
                aria-label={t("desktop.notices.closeUpdateNotice")}
                onClick={onCloseUpdateDialog}
              >
                <X size={16} strokeWidth={2} />
              </button>
            ) : null}
            {updateState.status === "checking" || updateState.status === "idle" ? (
              <div className="desktop-update-simple-state">
                <p className="desktop-notice-title">{t("desktop.notices.updateChecking")}</p>
                <p>{t("desktop.notices.updateCheckingDescription")}</p>
              </div>
            ) : null}
            {updateState.status === "not-available" ? (
              <div className="desktop-update-simple-state">
                <p className="desktop-notice-title">{t("desktop.notices.appUpToDate")}</p>
                <p>{t("desktop.notices.appUpToDateDescription")}</p>
              </div>
            ) : null}
            {hasVersionDetails ? (
              <>
                <div className="desktop-update-heading">
                  <p className="desktop-notice-title">
                    <PackageSearch size={16} strokeWidth={2} aria-hidden="true" />
                    {t("desktop.notices.updateFound")} <span>v{updateState.version}</span>
                  </p>
                  <button
                    className="desktop-notice-dismiss"
                    type="button"
                    aria-label={t("desktop.notices.closeUpdateNotice")}
                    onClick={onCloseUpdateDialog}
                  >
                    <X size={16} strokeWidth={2} />
                  </button>
                </div>
                <section className="desktop-update-release-section">
                  <div className="desktop-release-notes-header">
                    <button
                      className="desktop-release-notes-toggle"
                      type="button"
                      aria-expanded={releaseNotesOpen}
                      onClick={() => setReleaseNotesOpen((open) => !open)}
                    >
                      <span>{t("desktop.notices.releaseNotes")}</span>
                      <ChevronRight size={16} strokeWidth={2} />
                    </button>
                    <button className="desktop-release-details" type="button" onClick={onOpenRelease}>
                      {t("desktop.notices.viewDetails")}
                      <ExternalLink size={12} strokeWidth={2} aria-hidden="true" />
                    </button>
                  </div>
                  {releaseNotesOpen ? <ReleaseNotes releaseNotes={releaseNotes} /> : null}
                </section>
              </>
            ) : null}
            {updateState.status === "available" ? (
              <>
                <footer className="desktop-update-footer">
                  <button className="desktop-notice-primary" type="button" onClick={onDownloadUpdate}>
                    <Download size={15} strokeWidth={2} />
                    {t("desktop.notices.startDownload")}
                  </button>
                </footer>
              </>
            ) : null}
            {updateState.status === "downloading" ? (
              <section className="desktop-download-state">
                <div className="desktop-download-heading">
                  <span>{t("desktop.notices.downloading")}</span>
                  <button type="button" onClick={onCancelDownload}>
                    {t("desktop.common.cancel")}
                  </button>
                  <strong>{Math.round((updateState.progress ?? 0) * 100)}%</strong>
                </div>
                <div
                  className="desktop-update-progress"
                  aria-label={t("desktop.notices.downloadProgress", {
                    progress: Math.round((updateState.progress ?? 0) * 100),
                  })}
                >
                  <span style={{ width: `${Math.min(Math.max(updateState.progress ?? 0, 0), 1) * 100}%` }} />
                </div>
                <div className="desktop-download-metrics">
                  <span>{formatBytes(updateState.transferred)}</span>
                  <span>{formatBytes(updateState.bytesPerSecond)}/s</span>
                </div>
              </section>
            ) : null}
            {updateState.status === "downloaded" ? (
              <footer className="desktop-update-footer">
                <button className="desktop-notice-primary" type="button" onClick={onInstallUpdate}>
                  <RotateCcw size={15} strokeWidth={2} />
                  {t("desktop.notices.restartAndInstall")}
                </button>
              </footer>
            ) : null}
            {updateState.status === "error" ? (
              <div className="desktop-update-simple-state">
                <p className="desktop-notice-title">{t("desktop.notices.updateCheckFailed")}</p>
                <p>{updateState.message ?? t("desktop.notices.updateServiceUnavailable")}</p>
                <button className="desktop-notice-secondary" type="button" onClick={onCheckForUpdate}>
                  <RefreshCw size={15} strokeWidth={2} />
                  {t("desktop.notices.retry")}
                </button>
              </div>
            ) : null}
          </aside>
        </>
      ) : null}
    </>
  );
}
