import { useEffect, useState } from "react";
import { AlertTriangle, ClipboardList, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { DesktopInstance } from "../../shared/config";
import type { InstanceDeletionInfo } from "../../shared/ipc";
import "./instance-deletion-dialog.css";

interface InstanceDeletionDialogProps {
  instance: DesktopInstance | null;
  onClose: () => void;
  onConfirm: (instanceId: string, deleteData: boolean) => Promise<void>;
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function InstanceDeletionDialog({ instance, onClose, onConfirm }: InstanceDeletionDialogProps) {
  const { t } = useTranslation();
  const [info, setInfo] = useState<InstanceDeletionInfo | null>(null);
  const [deleteData, setDeleteData] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!instance) return;
    let cancelled = false;
    setInfo(null);
    setDeleteData(false);
    setLoading(true);
    setBusy(false);
    setClosing(false);
    setError(null);
    void window.openficDesktop
      .getInstanceDeletionInfo(instance.id)
      .then((nextInfo) => {
        if (!cancelled) setInfo(nextInfo);
      })
      .catch((nextError: unknown) => {
        if (!cancelled) setError(getErrorMessage(nextError));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [instance]);

  useEffect(() => {
    if (!instance || busy) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeDialog();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [busy, instance]);

  if (!instance) return null;

  const isLocal = instance.mode === "local";
  const closeDialog = () => {
    if (busy || closing) return;
    setClosing(true);
    window.setTimeout(onClose, 160);
  };

  const handleConfirm = async () => {
    if (!info || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onConfirm(instance.id, deleteData && !info.dataDirShared);
    } catch (nextError) {
      setError(getErrorMessage(nextError));
      setBusy(false);
    }
  };

  return (
    <div
      className={`instance-deletion-overlay${closing ? " is-closing" : ""}`}
      onClick={closeDialog}
    >
      <section
        className={`instance-deletion-dialog${closing ? " is-closing" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="instance-deletion-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="instance-deletion-head">
          <Trash2 size={16} strokeWidth={2} />
          <h2 id="instance-deletion-title">{t("desktop.instanceDeletion.title")}</h2>
        </div>
        <p className="instance-deletion-description">
          {t("desktop.instanceDeletion.description", { name: instance.name })}
        </p>

        {loading ? <p className="instance-deletion-status">{t("desktop.instanceDeletion.loading")}</p> : null}

        {isLocal && info ? (
          <div className="instance-deletion-details">
            <div>
              <span className="instance-deletion-label">{t("desktop.instanceDeletion.runtimeDirectory")}</span>
              <p title={info.runtimeDir ?? ""}>{info.runtimeDir}</p>
            </div>
            <div>
              <span className="instance-deletion-label">{t("desktop.instanceDeletion.dataDirectory")}</span>
              <p title={info.dataDir ?? ""}>{info.dataDir}</p>
            </div>
            <p className="instance-deletion-warning">
              <AlertTriangle size={14} strokeWidth={2} />
              <span>
                {info.runtimeDirShared
                  ? t("desktop.instanceDeletion.sharedRuntime")
                  : t("desktop.instanceDeletion.runtimeWarning")}
              </span>
            </p>
            <label className="instance-deletion-check" data-disabled={info.dataDirShared}>
              <input
                type="checkbox"
                checked={deleteData}
                disabled={info.dataDirShared || busy}
                onChange={(event) => setDeleteData(event.target.checked)}
              />
              <span>{t("desktop.instanceDeletion.clearData")}</span>
            </label>
            {info.dataDirShared ? (
              <p className="instance-deletion-hint">{t("desktop.instanceDeletion.sharedData")}</p>
            ) : null}
          </div>
        ) : null}

        {!isLocal ? <p className="instance-deletion-remote">{t("desktop.instanceDeletion.remoteDescription")}</p> : null}

        {error ? (
          <p className="instance-deletion-error">
            <AlertTriangle size={14} strokeWidth={2} />
            <span>{error}</span>
          </p>
        ) : null}

        <div className="instance-deletion-actions">
          <button className="instance-deletion-button" type="button" disabled={busy} onClick={closeDialog}>
            {t("desktop.common.cancel")}
          </button>
          <button
            className="instance-deletion-button instance-deletion-button-danger"
            type="button"
            disabled={loading || !info || busy || Boolean(error && !info)}
            onClick={() => void handleConfirm()}
          >
            <ClipboardList size={14} strokeWidth={2} />
            {busy ? t("desktop.instanceDeletion.deleting") : t("desktop.instanceDeletion.confirm")}
          </button>
        </div>
      </section>
    </div>
  );
}
