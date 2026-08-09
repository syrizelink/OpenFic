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
  RefreshCw,
  Upload,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { DataInfo } from "../../../shared/ipc";
import type { DesktopInstance } from "../../../shared/config";
import "./data-management.css";

interface DataManagementPageProps {
  instance: DesktopInstance | null;
  backendRunning: boolean;
  onClose: () => void;
  onConfigChanged: () => void;
}

type ConfirmKind = "migrate" | "attach" | "backup" | "restore";

interface ConfirmState {
  kind: ConfirmKind;
  path: string;
  text: string;
}

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** unitIndex;
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[unitIndex]}`;
}

function withRestartError(message: string, restartError?: string): string {
  if (!restartError) return message;
  return `${message}\n\n${restartError}`;
}

export function DataManagementPage({ instance, backendRunning, onClose, onConfigChanged }: DataManagementPageProps) {
  const { t } = useTranslation();
  const [dataInfo, setDataInfo] = useState<DataInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyLabel, setBusyLabel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [deleteOldDir, setDeleteOldDir] = useState(false);
  const [confirm, setConfirm] = useState<ConfirmState | null>(null);

  const backendNote = backendRunning ? `\n${t("desktop.data.backendRestartNote")}` : "";

  const refresh = useCallback(async () => {
    if (!instance) return;
    setLoading(true);
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

  const run = async (label: string, action: () => Promise<void>) => {
    setBusyLabel(label);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyLabel(null);
      setConfirm(null);
    }
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
          text: `${inspection.valid
            ? t("desktop.data.attachExistingConfirm", { path: picked })
            : t("desktop.data.attachNonEmptyConfirm", { path: picked })}${backendNote}`,
        });
        return;
      }
      setConfirm({
        kind: "migrate",
        path: picked,
        text: `${t("desktop.data.migrateConfirm", { from: dataInfo?.dataDir ?? "", to: picked })}${backendNote}`,
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
    setConfirm({ kind: "backup", path: target, text: `${t("desktop.data.backupConfirm", { path: target })}${backendNote}` });
  };

  const handleRestoreClick = async () => {
    setError(null);
    setNotice(null);
    const source = await window.openficDesktop.selectOpenFile();
    if (!source) return;
    setConfirm({
      kind: "restore",
      path: source,
      text: `${t("desktop.data.restoreConfirm", { path: source })}${backendNote}`,
    });
  };

  const executeConfirm = async () => {
    if (!confirm || !instance) return;
    if (confirm.kind === "migrate" || confirm.kind === "attach") {
      await run(t("desktop.data.migrating"), async () => {
        const result = await window.openficDesktop.migrateData(instance.id, confirm.path, confirm.kind === "migrate" && deleteOldDir);
        setNotice(
          withRestartError(
            result.migrated
              ? t("desktop.data.migrateDone", { path: result.dataDir })
              : t("desktop.data.attachDone", { path: result.dataDir }),
            result.restartError,
          ),
        );
        onConfigChanged();
        await refresh();
      });
      return;
    }
    if (confirm.kind === "backup") {
      await run(t("desktop.data.backingUp"), async () => {
        const result = await window.openficDesktop.backupData(instance.id, confirm.path);
        setNotice(withRestartError(t("desktop.data.backupDone", { path: confirm.path }), result.restartError));
      });
      return;
    }
    await run(t("desktop.data.restoring"), async () => {
      const result = await window.openficDesktop.restoreData(instance.id, confirm.path);
      setNotice(withRestartError(t("desktop.data.restoreDone", { path: confirm.path }), result.restartError));
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
          <button className="data-back" type="button" onClick={onClose}>
            <ChevronLeft size={16} strokeWidth={2} />
            {t("desktop.common.back")}
          </button>
        </div>

        {!instance ? (
          <div className="data-empty">{t("desktop.data.noActiveInstance")}</div>
        ) : instance.mode === "remote" ? (
          <>
            {heading}
            <div className="data-empty">{t("desktop.data.remoteUnsupported")}</div>
          </>
        ) : (
          <>
            {heading}

            <p className="data-description">{t("desktop.data.description")}</p>

            {loading ? (
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
              <div className="data-status">
                <span className="data-spinner" />
                <span>{busyLabel}</span>
              </div>
            ) : null}

            {confirm ? (
              <section className="data-confirm">
                <div className="data-confirm-head">
                  <ClipboardList size={15} strokeWidth={2} />
                  <span>{t("desktop.data.confirmTitle")}</span>
                </div>
                <p className="data-confirm-text">{confirm.text}</p>
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
                  <p className="data-confirm-warning">{t("desktop.data.restoreWarning")}</p>
                ) : null}
                <div className="data-confirm-actions">
                  <button className="data-btn" type="button" onClick={() => setConfirm(null)}>
                    {t("desktop.common.cancel")}
                  </button>
                  <button className="data-btn data-btn-primary" type="button" onClick={() => void executeConfirm()}>
                    {t("desktop.data.confirm")}
                  </button>
                </div>
              </section>
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