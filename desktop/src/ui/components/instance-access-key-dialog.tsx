import { useEffect, useState, type FormEvent } from "react";
import { AlertTriangle, LockKeyhole } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { DesktopInstance } from "../../shared/config";
import "./instance-access-key-dialog.css";

interface InstanceAccessKeyDialogProps {
  instance: DesktopInstance | null;
  onClose: () => void;
  onSave: (instanceId: string, accessKey: string) => Promise<void>;
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function InstanceAccessKeyDialog({ instance, onClose, onSave }: InstanceAccessKeyDialogProps) {
  const { t } = useTranslation();
  const [accessKey, setAccessKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!instance || busy || closing) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || busy || closing) return;
      setClosing(true);
      window.setTimeout(onClose, 160);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [busy, closing, instance, onClose]);

  if (!instance) return null;

  const closeDialog = () => {
    if (busy || closing) return;
    setClosing(true);
    window.setTimeout(onClose, 160);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await onSave(instance.id, accessKey);
      setBusy(false);
      setClosing(true);
      window.setTimeout(onClose, 160);
    } catch (saveError) {
      setError(getErrorMessage(saveError));
      setBusy(false);
    }
  };

  return (
    <div className={`instance-access-key-overlay${closing ? " is-closing" : ""}`} onClick={closeDialog}>
      <section
        className={`instance-access-key-dialog${closing ? " is-closing" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="instance-access-key-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="instance-access-key-head">
          <LockKeyhole size={16} strokeWidth={2} />
          <h2 id="instance-access-key-title">{t("desktop.instanceAccessKey.title")}</h2>
        </div>
        <p className="instance-access-key-description">{t("desktop.instanceAccessKey.description")}</p>
        <form className="instance-access-key-form" onSubmit={(event) => void handleSubmit(event)}>
          <label className="instance-access-key-field">
            <span>{t("desktop.instanceAccessKey.label")}</span>
            <input
              autoComplete="new-password"
              autoFocus
              disabled={busy}
              placeholder={t("desktop.instanceAccessKey.placeholder")}
              type="password"
              value={accessKey}
              onChange={(event) => setAccessKey(event.target.value)}
            />
          </label>
          <p className="instance-access-key-hint">
            {instance.hasAccessKey ? t("desktop.instanceAccessKey.configured") : t("desktop.instanceAccessKey.notConfigured")}
          </p>
          {error ? (
            <p className="instance-access-key-error">
              <AlertTriangle size={14} strokeWidth={2} />
              <span>{error}</span>
            </p>
          ) : null}
          <div className="instance-access-key-actions">
            <button className="instance-access-key-button" type="button" disabled={busy} onClick={closeDialog}>
              {t("desktop.common.cancel")}
            </button>
            <button className="instance-access-key-button instance-access-key-button-primary" type="submit" disabled={busy}>
              {busy ? t("desktop.instanceAccessKey.saving") : t("desktop.instanceAccessKey.save")}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
