import { IconButton, Tooltip, DropdownMenu } from "@radix-ui/themes";
import { Languages, Moon, Settings, Sun } from "lucide-react";
import { motion } from "motion/react";
import {
  SIDEBAR_ICON_COLOR,
  SIDEBAR_ICON_SIZE,
  sidebarActionButtonStyle,
} from "./app-sidebar.constants";

interface SidebarActionsProps {
  appearance: "light" | "dark";
  isExpanded: boolean;
  shouldAnimateTheme: boolean;
  languageLabel: string;
  settingsLabel: string;
  toggleThemeLabel: string;
  themeTooltip: string;
  languages: Array<{ code: string; name: string }>;
  currentLanguage: string;
  onLanguageChange: (language: string) => void;
  onToggleTheme: () => void;
  onOpenSettings: () => void;
}

export function SidebarActions({
  appearance,
  isExpanded,
  shouldAnimateTheme,
  languageLabel,
  settingsLabel,
  toggleThemeLabel,
  themeTooltip,
  languages,
  currentLanguage,
  onLanguageChange,
  onToggleTheme,
  onOpenSettings,
}: SidebarActionsProps) {
  const tooltipSide = isExpanded ? "top" : "right";

  return (
    <>
      <motion.div layout transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}>
        <DropdownMenu.Root>
          <Tooltip content={languageLabel} side={tooltipSide}>
            <DropdownMenu.Trigger>
              <IconButton
                variant="ghost"
                size="2"
                aria-label={languageLabel}
                style={sidebarActionButtonStyle}
              >
                <Languages size={SIDEBAR_ICON_SIZE} color="currentColor" />
              </IconButton>
            </DropdownMenu.Trigger>
          </Tooltip>
          <DropdownMenu.Content side={tooltipSide}>
            {languages.map((lang) => (
              <DropdownMenu.Item key={lang.code} onSelect={() => onLanguageChange(lang.code)}>
                {lang.name}
                {currentLanguage === lang.code && " ✓"}
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.Content>
        </DropdownMenu.Root>
      </motion.div>

      <motion.div layout transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}>
        <Tooltip side={tooltipSide} content={themeTooltip}>
          <IconButton
            variant="ghost"
            size="2"
            onClick={onToggleTheme}
            aria-label={toggleThemeLabel}
            style={sidebarActionButtonStyle}
          >
            <motion.div
              key={shouldAnimateTheme ? appearance : "static"}
              initial={shouldAnimateTheme ? { rotate: -90, opacity: 0 } : false}
              animate={{ rotate: 0, opacity: 1 }}
              transition={{ duration: 0.2 }}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {appearance === "light" ? (
                <Moon size={SIDEBAR_ICON_SIZE} color="currentColor" />
              ) : (
                <Sun size={SIDEBAR_ICON_SIZE} color="currentColor" />
              )}
            </motion.div>
          </IconButton>
        </Tooltip>
      </motion.div>

      <motion.div layout transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}>
        <Tooltip content={settingsLabel} side={tooltipSide}>
          <IconButton
            variant="ghost"
            size="2"
            onClick={onOpenSettings}
            aria-label={settingsLabel}
            style={{
              ...sidebarActionButtonStyle,
              color: SIDEBAR_ICON_COLOR,
            }}
          >
            <Settings size={SIDEBAR_ICON_SIZE} color="currentColor" />
          </IconButton>
        </Tooltip>
      </motion.div>
    </>
  );
}
