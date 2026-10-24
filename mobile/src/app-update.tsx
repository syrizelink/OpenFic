import { Button, Dialog } from "@radix-ui/themes";
import { useEffect, useRef, useState } from "react";

import { toast } from "../../frontend/src/components/toast";
import { AppUpdate, supportsAppUpdates, type UpdateState } from "./native";

type UpdateDialog = "available" | "ready" | null;

function UpdateProgress({ progress }: { progress: number }) {
  const value = Math.max(0, Math.min(100, progress));
  const accessibleValue = Math.round(value);
  const circumference = 2 * Math.PI * 10;
  const offset = circumference * (1 - value / 100);

  return (
    <span
      className="mobile-update-circle"
      aria-label={`下载进度 ${accessibleValue}%`}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={accessibleValue}
    >
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle
          className="mobile-update-circle-track"
          cx="12"
          cy="12"
          r="10"
        />
        <circle
          className="mobile-update-circle-value"
          cx="12"
          cy="12"
          r="10"
          strokeDasharray={circumference}
          style={{ strokeDashoffset: offset }}
        />
      </svg>
    </span>
  );
}

export function AppUpdatePanel() {
  const [update, setUpdate] = useState<UpdateState>({
    status: supportsAppUpdates ? "idle" : "unsupported",
  });
  const [dialog, setDialog] = useState<UpdateDialog>(null);
  const [installing, setInstalling] = useState(false);
  const isCheckingRef = useRef(false);
  const isDownloadingRef = useRef(false);
  const isInstallingRef = useRef(false);

  useEffect(() => {
    if (!supportsAppUpdates) return;
    let disposed = false;
    async function checkOnStartup() {
      try {
        const current = await AppUpdate.getStatus();
        if (disposed) return;
        setUpdate(current);
        if (current.status === "available" || current.status === "ready") {
          setDialog(current.status);
          return;
        }
        if (current.status === "downloading") return;
        const next = await AppUpdate.check();
        if (disposed) return;
        setUpdate(next);
        if (next.status === "available") setDialog("available");
      } catch {
        // Startup checks stay silent; manual checks report errors through toast.
      }
    }
    void checkOnStartup();
    return () => {
      disposed = true;
    };
  }, []);

  useEffect(() => {
    if (update.status !== "downloading") return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const next = await AppUpdate.getStatus();
        if (disposed) return;
        setUpdate(next);
        if (next.status === "ready") {
          setDialog("ready");
          return;
        }
        if (next.status === "downloading") timer = setTimeout(() => void poll(), 250);
      } catch (cause) {
        if (!disposed) {
          setUpdate({
            status: "error",
            message: cause instanceof Error ? cause.message : "读取下载状态失败。",
          });
          toast.error("读取下载状态失败。", { id: "mobile-update-status" });
        }
      }
    }

    timer = setTimeout(() => void poll(), 250);
    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
    };
  }, [update.status]);

  async function handleCheck() {
    if (!supportsAppUpdates) {
      toast.error("当前环境不支持应用更新。", { id: "mobile-update-check" });
      return;
    }
    if (isCheckingRef.current || isDownloadingRef.current) return;
    isCheckingRef.current = true;
    setUpdate((current) => ({ ...current, status: "checking", message: undefined }));
    try {
      const next = await AppUpdate.check();
      setUpdate(next);
      if (next.status === "idle") {
        toast.success("当前已是最新版本。", { id: "mobile-update-check" });
      } else if (next.status === "error") {
        toast.error(next.message ?? "检查更新失败。", { id: "mobile-update-check" });
      } else if (next.status === "available") {
        setDialog("available");
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "检查更新失败。";
      setUpdate({ status: "error", message });
      toast.error(message, { id: "mobile-update-check" });
    } finally {
      isCheckingRef.current = false;
    }
  }

  async function handleDownload() {
    if (isDownloadingRef.current) return;
    isDownloadingRef.current = true;
    try {
      const next = await AppUpdate.download();
      setUpdate(next);
      setDialog(next.status === "ready" ? "ready" : null);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "开始下载失败。";
      setUpdate({ status: "error", message });
      toast.error(message, { id: "mobile-update-download" });
    } finally {
      isDownloadingRef.current = false;
    }
  }

  async function handleInstall() {
    if (isInstallingRef.current) return;
    isInstallingRef.current = true;
    setInstalling(true);
    try {
      const result = await AppUpdate.install();
      if (result.permissionRequired) {
        toast.info("请允许 OpenFic 安装未知应用，返回后再次点击安装更新。", {
          id: "mobile-update-install",
        });
      } else {
        setDialog(null);
        toast.info("请在系统安装界面确认更新。", { id: "mobile-update-install" });
      }
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "无法安装更新，请重试。", {
        id: "mobile-update-install",
      });
    } finally {
      isInstallingRef.current = false;
      setInstalling(false);
    }
  }

  const isChecking = update.status === "checking";
  const isDownloading = update.status === "downloading";
  const isReady = update.status === "ready";

  return (
    <>
      <button
        className="mobile-about-row mobile-update-check-row"
        type="button"
        disabled={isChecking || isDownloading || installing}
        onClick={() => {
          if (isReady) void handleInstall();
          else void handleCheck();
        }}
      >
        <span>检查更新</span>
        {isDownloading ? (
          <UpdateProgress progress={update.progress ?? 0} />
        ) : isChecking ? (
          <span
            className="mobile-update-spinner"
            aria-label="正在检查更新"
          />
        ) : isReady ? (
          <span className="mobile-update-action-label">安装更新</span>
        ) : update.status === "error" ? (
          <span className="mobile-update-action-label">重试</span>
        ) : null}
      </button>

      <Dialog.Root
        open={dialog === "available"}
        onOpenChange={(open) => {
          if (!open) setDialog(null);
        }}
      >
        <Dialog.Content maxWidth="400px">
          <Dialog.Title>发现新版本</Dialog.Title>
          <Dialog.Description>v{update.version} 已发布，是否下载更新安装包？</Dialog.Description>
          <div className="mobile-dialog-actions">
            <Button
              variant="soft"
              onClick={() => setDialog(null)}
            >
              稍后
            </Button>
            <Button onClick={() => void handleDownload()}>下载更新</Button>
          </div>
        </Dialog.Content>
      </Dialog.Root>

      <Dialog.Root
        open={dialog === "ready"}
        onOpenChange={(open) => {
          if (!open) setDialog(null);
        }}
      >
        <Dialog.Content maxWidth="400px">
          <Dialog.Title>更新已下载</Dialog.Title>
          <Dialog.Description>
            v{update.version} 已下载并完成校验，是否立即安装？
          </Dialog.Description>
          <div className="mobile-dialog-actions">
            <Button
              variant="soft"
              onClick={() => setDialog(null)}
            >
              稍后
            </Button>
            <Button
              disabled={installing}
              onClick={() => void handleInstall()}
            >
              安装更新
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Root>
    </>
  );
}
