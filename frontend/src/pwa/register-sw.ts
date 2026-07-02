import i18n from "i18next";
import { toast } from "sonner";

export function registerSW(): void {
  if (!import.meta.env.PROD) {
    return;
  }

  if (typeof window !== "undefined" && "openficDesktopHost" in window) {
    return;
  }

  if (!("serviceWorker" in navigator)) {
    return;
  }

  let hasPreviousController = navigator.serviceWorker.controller !== null;

  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (hasPreviousController) {
      toast(i18n.t("common.swUpdated"), {
        action: {
          label: i18n.t("common.refresh"),
          onClick: () => window.location.reload(),
        },
      });
    }
    hasPreviousController = true;
  });

  navigator.serviceWorker.register("/sw.js").catch((error) => {
    console.warn("Service Worker 注册失败:", error);
  });
}
