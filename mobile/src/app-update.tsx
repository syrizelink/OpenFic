import { Button, Dialog } from "@radix-ui/themes";
import { useEffect, useState } from "react";

import { AppUpdate, supportsAppUpdates, type UpdateState } from "./native";

export function AppUpdatePanel() {
  const [update, setUpdate] = useState<UpdateState>({
    status: supportsAppUpdates ? "checking" : "unsupported",
  });
  const [dismissedVersion, setDismissedVersion] = useState<string>();
  const [installing, setInstalling] = useState(false);
  const [installMessage, setInstallMessage] = useState("");

  useEffect(() => {
    if (!supportsAppUpdates) return;
    let disposed = false;
    async function check() {
      try {
        const next = await AppUpdate.check();
        if (disposed) return;
        setUpdate(next);
      } catch (cause) {
        if (!disposed)
          setUpdate({
            status: "error",
            message: cause instanceof Error ? cause.message : "检查更新失败。",
          });
      }
    }
    void check();
    return () => {
      disposed = true;
    };
  }, []);

  useEffect(() => {
    if (update.status !== "downloading") return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await AppUpdate.getStatus();
        if (disposed) return;
        setUpdate(next);
        if (next.status === "downloading") timer = setTimeout(() => void poll(), 1500);
      } catch (cause) {
        if (!disposed)
          setUpdate({
            status: "error",
            message: cause instanceof Error ? cause.message : "读取下载状态失败。",
          });
      }
    }
    timer = setTimeout(() => void poll(), 1500);
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [update.status]);

  async function handleCheck() {
    setInstallMessage("");
    setUpdate((current) => ({ ...current, status: "checking" }));
    try {
      setUpdate(await AppUpdate.check());
    } catch (cause) {
      setUpdate({
        status: "error",
        message: cause instanceof Error ? cause.message : "检查更新失败。",
      });
    }
  }

  async function handleInstall() {
    setInstalling(true);
    setInstallMessage("");
    try {
      const result = await AppUpdate.install();
      setInstallMessage(
        result.permissionRequired
          ? "请允许 OpenFic 安装未知应用，返回后再次点击“安装更新”。"
          : "请在系统安装界面确认安装；若已取消，可再次点击安装。",
      );
    } catch (cause) {
      setInstallMessage(cause instanceof Error ? cause.message : "无法安装更新，请重试。");
    } finally {
      setInstalling(false);
    }
  }

  if (update.status === "unsupported") return null;
  const isBusy = update.status === "checking" || update.status === "downloading";
  const title =
    update.status === "checking"
      ? "正在检查更新…"
      : update.status === "downloading"
        ? `正在下载 OpenFic ${update.version}`
        : update.status === "ready"
          ? `OpenFic ${update.version} 已准备安装`
          : update.status === "error"
            ? "应用更新失败"
            : "应用更新";

  return (
    <section
      className="mobile-update"
      aria-label="应用更新"
    >
      <h2>{title}</h2>
      <p role="status">
        {update.message ||
          (update.status === "ready"
            ? "安装包已校验，安装需要你在系统界面确认。"
            : "正在连接 GitHub Release。")}
      </p>
      {update.status === "downloading" && (
        <div className="mobile-update-progress">
          <progress
            value={update.progress ?? 0}
            max={100}
            aria-label="更新下载进度"
          />
          <span>{update.progress ?? 0}%</span>
        </div>
      )}
      {update.currentVersion && <p>当前版本：{update.currentVersion}</p>}
      {installMessage && <p role="status">{installMessage}</p>}
      <div className="mobile-update-actions">
        {update.status === "ready" && (
          <Button
            size="2"
            disabled={installing}
            onClick={() => void handleInstall()}
          >
            安装更新
          </Button>
        )}
        <Button
          size="2"
          variant="soft"
          disabled={isBusy || installing}
          onClick={() => void handleCheck()}
        >
          {update.status === "error" ? "重试更新" : "检查更新"}
        </Button>
      </div>
      <Dialog.Root
        open={update.status === "ready" && update.version !== dismissedVersion}
        onOpenChange={(open) => {
          if (!open) setDismissedVersion(update.version);
        }}
      >
        <Dialog.Content maxWidth="400px">
          <Dialog.Title>新版本已下载</Dialog.Title>
          <Dialog.Description>
            OpenFic {update.version}{" "}
            已通过校验。安装时会打开系统确认界面，远程实例中的创作数据不会受影响。
          </Dialog.Description>
          <div className="mobile-dialog-actions">
            <Dialog.Close>
              <Button variant="soft">稍后安装</Button>
            </Dialog.Close>
            <Button
              disabled={installing}
              onClick={() => {
                setDismissedVersion(update.version);
                void handleInstall();
              }}
            >
              安装更新
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Root>
    </section>
  );
}
