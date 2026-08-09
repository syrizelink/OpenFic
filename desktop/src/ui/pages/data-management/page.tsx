import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Archive,
  Check,
  ChevronLeft,
  ClipboardList,
  Database,
  FolderOpen,
  HardDrive,
  Link2,
  RefreshCw,
  Upload,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { DataInfo, DataProgressEvent } from "../../../shared/ipc";
import type { DesktopInstance } from "../../../shared/config";
import "./data-management.css";

interface DataManagementPageProps {
  instanceId: string | null;
  instances: DesktopInstance[];
  backendRunning: boolean;
  onSelectInstance: (instanceId: string) => void;
  onClose: () => void;
  onConfigChanged: () => void;
}

type ConfirmKind = "migrate" | "attach" | "backup" | "restore";

interface ConfirmState {
  kind: ConfirmKind;
  path: string;
  textBefore: string;
  textAfter?: string;
}

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** unitIndex;
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[unitIndex]}`;
}

export function DataManagementPage({
  instanceId,
  instances,
  backendRunning,
  onSelectInstance,
  onClose,
  onConfigChanged,
}: DataManagementPageProps) {
  const { t } = useTranslation();
  const instance = instances.find((item) => item.id === instanceId) ?? null;
  const localInstances = instances.filter((item) => item.mode === "local");
  const [dataInfo, setDataInfo] = useState<DataInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyLabel, setBusyLabel] = useState<string | null>(null);
  const [progress, setProgress] = useState<DataProgressEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [deleteOldDir, setDeleteOldDir] = useState(false);
  const [confirm, setConfirm] = useState<ConfirmState | null>(null);
  const [confirmClosing, setConfirmClosing] = useState(false);

  const backendNote = backendRunning ? `${t("desktop.data.backendRestartNote")}` : "";
  const backendStoppedNote = backendRunning ? `\n${t("desktop.data.backendStoppedNote")}` : "";

  const refresh = useCallback(async () => {
    if (!instance) return;
    setError(null);
    try {
      const info = await window.openficDesktop.getDataInfo(instance.id);
      setDataInfo(info);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [instance]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!busyLabel) return;
    setProgress(null);
    return window.openficDesktop.onDataProgress(setProgress);
  }, [busyLabel]);

  useEffect(() => {
    if (!confirm) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeConfirm();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [confirm, confirmClosing]);

  const run = async (label: string, action: () => Promise<void>) => {
    setConfirm(null);
    setConfirmClosing(false);
    setBusyLabel(label);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyLabel(null);
    }
  };

  const closeConfirm = () => {
    if (confirmClosing) return;
    setConfirmClosing(true);
    window.setTimeout(() => {
      setConfirm(null);
      setConfirmClosing(false);
    }, 160);
  };

  const handleMigrateClick = async () => {
    setError(null);
    setNotice(null);
    const picked = await window.openficDesktop.selectDirectory();
    if (!picked) return;
    try {
      const inspection = await window.openficDesktop.inspectDataDir(picked);
      if (inspection.hasData) {
        setConfirm({
          kind: "attach",
          path: picked,
          textBefore: inspection.valid
            ? t("desktop.data.attachExistingConfirmBefore")
            : t("desktop.data.attachNonEmptyConfirmBefore"),
          textAfter: `${t("desktop.data.attachConfirmAfter")}\n${backendNote}`,
        });
        return;
      }
      setConfirm({
        kind: "migrate",
        path: picked,
        textBefore: t("desktop.data.migrateConfirmBefore")
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleBackupClick = async () => {
    setError(null);
    setNotice(null);
    const target = await window.openficDesktop.selectSaveFile();
    if (!target) return;
    setConfirm({ kind: "backup", path: target, textBefore: t("desktop.data.backupConfirmBefore"), textAfter: backendNote });
  };

  const handleRestoreClick = async () => {
    setError(null);
    setNotice(null);
    const source = await window.openficDesktop.selectOpenFile();
    if (!source) return;
    setConfirm({
      kind: "restore",
      path: source,
      textBefore: t("desktop.data.restoreConfirmBefore")
    });
  };

  const executeConfirm = async () => {
    if (!confirm || !instance) return;
    if (confirm.kind === "migrate" || confirm.kind === "attach") {
      await run(t("desktop.data.migrating"), async () => {
        const result = await window.openficDesktop.migrateData(instance.id, confirm.path, confirm.kind === "migrate" && deleteOldDir);
        setNotice(
          `${result.migrated
            ? t("desktop.data.migrateDone", { path: result.dataDir })
            : t("desktop.data.attachDone", { path: result.dataDir })}\n${backendStoppedNote}`,
        );
        onConfigChanged();
        await refresh();
      });
      return;
    }
    if (confirm.kind === "backup") {
      await run(t("desktop.data.backingUp"), async () => {
        await window.openficDesktop.backupData(instance.id, confirm.path);
        setNotice(`${t("desktop.data.backupDone", { path: confirm.path })}\n${backendStoppedNote}`);
      });
      return;
    }
    await run(t("desktop.data.restoring"), async () => {
      await window.openficDesktop.restoreData(instance.id, confirm.path);
      setNotice(`${t("desktop.data.restoreDone", { path: confirm.path })}\n${backendStoppedNote}`);
    });
  };

  const heading = (
    <>
      <div className="data-heading">
        <Database size={17} strokeWidth={2} />
        <h2>{t("desktop.data.title")}</h2>
        {instance ? <span className="data-instance-name">{instance.name}</span> : null}
      </div>
    </>
  );

  return (
    <section className="content-page content-page-centered">
      <section className="data-page">
        <div className="data-page-top">
          <button className="data-back" type="button" disabled={Boolean(busyLabel)} onClick={onClose}>
            <ChevronLeft size={16} strokeWidth={2} />
            {t("desktop.common.back")}
          </button>
        </div>

        {!instance ? (
          <>
            {heading}
            {localInstances.length ? (
              <>
                <p className="data-description">{t("desktop.data.selectInstance")}</p>
                <div className="data-instance-list">
                  {localInstances.map((item) => (
                    <button
                      className="data-instance-item"
                      type="button"
                      key={item.id}
                      onClick={() => onSelectInstance(item.id)}
                    >
                      <span className="data-instance-item-icon">
                        <HardDrive size={15} strokeWidth={2} />
                      </span>
                      <span className="data-instance-item-copy">
                        <strong>{item.name}</strong>
                        <span title={item.installDir ?? ""}>
                          {item.installDir ?? t("desktop.data.installDirNotSet")}
                        </span>
                      </span>
                      <Link2 size={14} strokeWidth={2} />
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <div className="data-empty">{t("desktop.data.noActiveInstance")}</div>
            )}
          </>
        ) : instance.mode === "remote" ? (
          <>
            {heading}
            <div className="data-empty">{t("desktop.data.remoteUnsupported")}</div>
          </>
        ) : (
          <>
            {heading}

            <p className="data-description">{t("desktop.data.description")}</p>

            {loading && !dataInfo ? (
              <div className="data-status">
                <span className="data-spinner" />
                <span>{t("desktop.data.reading")}</span>
              </div>
            ) : dataInfo ? (
              <section className="data-card">
                <div className="data-card-head">
                  <HardDrive size={15} strokeWidth={2} />
                  <span>{t("desktop.data.currentLocation")}</span>
                  {dataInfo.isDefaultLocation ? <span className="data-badge">{t("desktop.data.defaultLocation")}</span> : null}
                </div>
                <p className="data-path" title={dataInfo.dataDir}>{dataInfo.dataDir}</p>
                <div className="data-meta">
                  <span>{t("desktop.data.entries", { count: dataInfo.entryCount })}</span>
                  <span>{formatBytes(dataInfo.sizeBytes)}</span>
                </div>
              </section>
            ) : null}

            {error ? (
              <div className="data-alert data-alert-error">
                <AlertTriangle size={15} strokeWidth={2} />
                <span>{error}</span>
              </div>
            ) : null}
            {notice ? (
              <div className="data-alert data-alert-success">
                <Check size={15} strokeWidth={2.5} />
                <span>{notice}</span>
              </div>
            ) : null}

            {busyLabel ? (
              <div className="data-status data-status-progress">
                <span className="data-spinner" />
                <span>
                  {progress
                    ? t(`desktop.data.progress.${progress.operation}.${progress.phase}`)
                    : busyLabel}
                </span>
                {progress?.progress != null ? (
                  <span className="data-progress-track">
                    <span
                      className="data-progress-bar"
                      style={{ width: `${Math.round(progress.progress * 100)}%` }}
                    />
                  </span>
                ) : null}
              </div>
            ) : null}

            {confirm ? (
              <div
                className={`data-dialog-overlay${confirmClosing ? " is-closing" : ""}`}
                onClick={closeConfirm}
              >
                <section
                  className={`data-dialog${confirmClosing ? " is-closing" : ""}`}
                  role="dialog"
                  aria-modal="true"
                  aria-label={t("desktop.data.confirmTitle")}
                  onClick={(event) => event.stopPropagation()}
                >
                  <div className="data-dialog-head">
                    <ClipboardList size={15} strokeWidth={2} />
                    <span>{t("desktop.data.confirmTitle")}</span>
                  </div>
                  <div className="data-dialog-flow">
                    <p className="data-dialog-text">{confirm.textBefore}</p>
                    <div className="data-dialog-path" title={confirm.path}>
                      {confirm.path}
                    </div>
                    {confirm.textAfter ? <p className="data-dialog-text">{confirm.textAfter}</p> : null}
                  </div>
                  {confirm.kind === "migrate" ? (
                    <label className="data-check">
                      <input
                        type="checkbox"
                        checked={deleteOldDir}
                        onChange={(event) => setDeleteOldDir(event.target.checked)}
                      />
                      <span>{t("desktop.data.deleteOldDir")}</span>
                    </label>
                  ) : null}
                  {confirm.kind === "restore" ? (
                    <p className="data-dialog-warning">{t("desktop.data.restoreWarning")}</p>
                  ) : null}
                  <div className="data-dialog-actions">
                    <button className="data-btn" type="button" disabled={Boolean(busyLabel)} onClick={closeConfirm}>
                      {t("desktop.common.cancel")}
                    </button>
                    <button
                      className="data-btn data-btn-primary"
                      type="button"
                      disabled={Boolean(busyLabel)}
                      onClick={() => void executeConfirm()}
                    >
                      {t("desktop.data.confirm")}
                    </button>
                  </div>
                </section>
              </div>
            ) : null}

            <footer className="data-actions">
              <button className="data-btn" type="button" disabled={Boolean(busyLabel)} onClick={() => void handleMigrateClick()}>
                <FolderOpen size={15} strokeWidth={2} />
                {t("desktop.data.migrate")}
              </button>
              <button className="data-btn" type="button" disabled={Boolean(busyLabel)} onClick={() => void handleBackupClick()}>
                <Archive size={15} strokeWidth={2} />
                {t("desktop.data.backup")}
              </button>
              <button className="data-btn" type="button" disabled={Boolean(busyLabel)} onClick={() => void handleRestoreClick()}>
                <Upload size={15} strokeWidth={2} />
                {t("desktop.data.restore")}
              </button>
              <button className="data-btn" type="button" disabled={Boolean(busyLabel)} onClick={() => void refresh()}>
                <RefreshCw size={15} strokeWidth={2} />
                {t("desktop.data.refresh")}
              </button>
            </footer>
          </>
        )}
      </section>
    </section>
  );
}