import { IconButton, Tooltip } from "@radix-ui/themes";
import { PanelLeft } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAppShell } from "./app-shell-context";

export function MobileAppSidebarTrigger() {
  const { t } = useTranslation();
  const { isMobile, openSidebar } = useAppShell();

  if (!isMobile) return null;

  return (
    <Tooltip content={t("topbar.expand")}>
      <IconButton
        variant="ghost"
        size="2"
        aria-label={t("topbar.expand")}
        onClick={openSidebar}
      >
        <PanelLeft size={18} />
      </IconButton>
    </Tooltip>
  );
}
