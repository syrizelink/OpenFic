import { Button } from "@radix-ui/themes";
import { useEffect, useState } from "react";

import { toast } from "../../frontend/src/components/toast";
import { AppUpdate, supportsAppUpdates, type UpdateState } from "./native";

export function AppUpdatePanel() {
  const [update, setUpdate] = useState<UpdateState>({
    status: supportsAppUpdates ? "checking" : "unsupported",
  });
  const [installing, setInstalling] = useState(false);

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
    if (update.status !== "downloading" && update.status !== "available") return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await AppUpdate.getStatus();
        if (disposed) return;
        if (next.status === "ready" && update.status === "downloading")
          toast.success("更新安装包已下载并校验，请在关于页面安装。", {
            id: "mobile-update-ready",
          });
        setUpdate(next);
        if (next.status === "downloading" || next.status === "available")
          timer = setTimeout(() => void poll(), 1500);
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
    setUpdate((current) => ({ ...current, status: "checking" }));
    try {
      const next = await AppUpdate.check();
      setUpdate(next);
      if (next.status === "idle")
        toast.success("当前已是最新版本。", { id: "mobile-update-check" });
      if (next.status === "error")
        toast.error(next.message ?? "检查更新失败。", { id: "mobile-update-check" });
    } catch (cause) {
      setUpdate({
        status: "error",
        message: cause instanceof Error ? cause.message : "检查更新失败。",
      });
    }
  }

  async function handleDownload() {
    setUpdate((current) => ({ ...current, status: "checking" }));
    try {
      setUpdate(await AppUpdate.download());
    } catch (cause) {
      setUpdate({
        status: "error",
        message: cause instanceof Error ? cause.message : "开始下载失败。",
      });
    }
  }

  async function handleInstall() {
    setInstalling(true);
    try {
      const result = await AppUpdate.install();
      toast.info(
        result.permissionRequired
          ? "请允许 OpenFic 安装未知应用，返回后再次点击“安装更新”。"
          : "请在系统安装界面确认安装；若已取消，可再次点击安装。",
        { id: "mobile-update-install" },
      );
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "无法安装更新，请重试。", {
        id: "mobile-update-install",
      });
    } finally {
      setInstalling(false);
    }
  }

  if (update.status === "unsupported")
    return <p className="mobile-about-row">请在 Android App 中检查更新。</p>;
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
            : update.status === "available"
              ? "新版本已发布，点击后开始下载。"
              : update.status === "idle"
                ? "当前已是最新版本。"
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
      <div className="mobile-update-actions">
        {update.status === "available" && (
          <Button
            size="2"
            onClick={() => void handleDownload()}
          >
            下载更新
          </Button>
        )}
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
    </section>
  );
}
