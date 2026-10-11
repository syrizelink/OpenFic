import { Tooltip } from "radix-ui";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Toaster as SonnerToaster } from "sonner";

const MOBILE_VIEWPORT_QUERY = "(max-width: 767px)";

interface ToasterProps {
  appearance: "light" | "dark";
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

export function Toaster({ appearance }: ToasterProps) {
  const isMobileViewport = useIsMobileViewport();

  return createPortal(
    <Tooltip.Provider delayDuration={200}>
      <SonnerToaster
        position={isMobileViewport ? "top-center" : "bottom-center"}
        closeButton
        theme={appearance}
        style={{ zIndex: 2147483647, pointerEvents: "auto" }}
      />
    </Tooltip.Provider>,
    document.body,
  );
}
