import { Tooltip } from "radix-ui";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Toaster as SonnerToaster } from "sonner";

import { toast } from "./toast";

const MOBILE_VIEWPORT_QUERY = "(max-width: 767px)";

interface ToasterProps {
  appearance: "light" | "dark";
  position?: "top-center" | "bottom-center";
  visibleToasts?: number;
}

function useIsMobileViewport(): boolean {
  const [isMobileViewport, setIsMobileViewport] = useState(
    () => typeof window !== "undefined" && window.matchMedia(MOBILE_VIEWPORT_QUERY).matches,
  );

  useEffect(() => {
    const mediaQuery = window.matchMedia(MOBILE_VIEWPORT_QUERY);
    const handleChange = () => setIsMobileViewport(mediaQuery.matches);

    handleChange();
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  return isMobileViewport;
}

export function Toaster({ appearance, position, visibleToasts }: ToasterProps) {
  const isMobileViewport = useIsMobileViewport();
  useEffect(() => {
    const host = window as Window & {
      OpenFicAppearance?: { postMessage: (value: string) => void };
    };
    const publish = () =>
      host.OpenFicAppearance?.postMessage(
        JSON.stringify({
          appearance,
          background: getComputedStyle(document.documentElement)
            .getPropertyValue("--theme-background")
            .trim(),
        }),
      );
    publish();
    const observer = new MutationObserver(publish);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["style"] });
    return () => observer.disconnect();
  }, [appearance]);
  useEffect(() => {
    const handleNotice = (event: Event) => {
      const detail = (event as CustomEvent<{ message?: unknown; error?: boolean }>).detail;
      if (typeof detail?.message !== "string") return;
      const id = `native-notice-${detail.error ? "error" : "success"}-${detail.message}`;
      if (detail.error) toast.error(detail.message, { id });
      else toast.success(detail.message, { id });
    };
    window.addEventListener("openfic:native-notice", handleNotice);
    return () => window.removeEventListener("openfic:native-notice", handleNotice);
  }, []);

  return createPortal(
    <Tooltip.Provider delayDuration={200}>
      <SonnerToaster
        position={position ?? (isMobileViewport ? "top-center" : "bottom-center")}
        visibleToasts={visibleToasts}
        closeButton
        offset={{
          top: "calc(var(--mobile-safe-top, 0px) + 16px)",
          bottom: "calc(var(--mobile-safe-bottom, 0px) + 16px)",
        }}
        mobileOffset={{
          top: "calc(var(--mobile-safe-top, 0px) + 16px)",
          bottom: "calc(var(--mobile-safe-bottom, 0px) + 16px)",
        }}
        theme={appearance}
        style={{ zIndex: 2147483647, pointerEvents: "auto" }}
      />
    </Tooltip.Provider>,
    document.body,
  );
}
