import { Dialog } from "@radix-ui/themes";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import "./settings-dialog.css";

import type { ThemeMode, ThemeSettings } from "@/lib/theme";

import type { SettingsDialogRoute } from "../lib/settings-route";
import { SettingsContent } from "./settings-content";

interface SettingsDialogProps {
  themeMode: ThemeMode;
  onThemeModeChange: (themeMode: ThemeMode) => void;
  onThemeSettingsChange: (settings: ThemeSettings) => void;
  onThemePreviewChange: (settings: ThemeSettings) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  route?: SettingsDialogRoute;
}

export function SettingsDialog({
  themeMode,
  onThemeModeChange,
  onThemeSettingsChange,
  onThemePreviewChange,
  open,
  onOpenChange,
  route,
}: SettingsDialogProps) {
  const { t } = useTranslation();
  const routeKey = `${open ? "open" : "closed"}:${route?.category ?? "default"}:${route?.modelTab ?? ""}`;
  const dropdownOpenAtPointerDownRef = useRef(false);

  useEffect(() => {
    const handlePointerDown = () => {
      dropdownOpenAtPointerDownRef.current =
        document.querySelector("[data-radix-select-viewport]") !== null ||
        document.querySelector("[data-radix-popper-content-wrapper]") !== null;
    };
    document.addEventListener("pointerdown", handlePointerDown, true);
    return () => document.removeEventListener("pointerdown", handlePointerDown, true);
  }, []);

  return (
    <Dialog.Root
      open={open}
      onOpenChange={onOpenChange}
    >
      <Dialog.Content
        className="settings-dialog-surface"
        maxWidth="1180px"
        onInteractOutside={(event) => {
          if (dropdownOpenAtPointerDownRef.current) {
            dropdownOpenAtPointerDownRef.current = false;
            event.preventDefault();
          }
        }}
      >
        <Dialog.Title className="settings-dialog-visually-hidden">
          {t("topbar.settings")}
        </Dialog.Title>
        <Dialog.Description className="settings-dialog-visually-hidden">
          {t("topbar.settings")}
        </Dialog.Description>

        <SettingsContent
          key={routeKey}
          themeMode={themeMode}
          onThemeModeChange={onThemeModeChange}
          onThemeSettingsChange={onThemeSettingsChange}
          onThemePreviewChange={onThemePreviewChange}
          onClose={() => onOpenChange(false)}
          route={route}
        />
      </Dialog.Content>
    </Dialog.Root>
  );
}
