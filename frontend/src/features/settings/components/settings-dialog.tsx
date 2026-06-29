import { Dialog } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import "./settings-dialog.css";

import { SettingsContent } from "./settings-content";
import type { SettingsDialogRoute } from "../lib/settings-route";

interface SettingsDialogProps {
  appearance: "light" | "dark";
  open: boolean;
  onOpenChange: (open: boolean) => void;
  route?: SettingsDialogRoute;
}

export function SettingsDialog({ appearance, open, onOpenChange, route }: SettingsDialogProps) {
  const { t } = useTranslation();
  const routeKey = `${open ? "open" : "closed"}:${route?.category ?? "default"}:${route?.modelTab ?? ""}`;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content className="settings-dialog-surface" maxWidth="1180px">
        <Dialog.Title className="settings-dialog-visually-hidden">
          {t("topbar.settings")}
        </Dialog.Title>
        <Dialog.Description className="settings-dialog-visually-hidden">
          {t("topbar.settings")}
        </Dialog.Description>

        <SettingsContent
          key={routeKey}
          appearance={appearance}
          onClose={() => onOpenChange(false)}
          route={route}
        />
      </Dialog.Content>
    </Dialog.Root>
  );
}
