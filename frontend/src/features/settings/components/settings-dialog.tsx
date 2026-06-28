import { Dialog } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import "./settings-dialog.css";

import { SettingsContent } from "./settings-content";

interface SettingsDialogProps {
  appearance: "light" | "dark";
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SettingsDialog({ appearance, open, onOpenChange }: SettingsDialogProps) {
  const { t } = useTranslation();

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content className="settings-dialog-surface" maxWidth="1180px">
        <Dialog.Title className="settings-dialog-visually-hidden">
          {t("topbar.settings")}
        </Dialog.Title>
        <Dialog.Description className="settings-dialog-visually-hidden">
          {t("topbar.settings")}
        </Dialog.Description>

        <SettingsContent appearance={appearance} onClose={() => onOpenChange(false)} />
      </Dialog.Content>
    </Dialog.Root>
  );
}
