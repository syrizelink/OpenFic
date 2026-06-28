import { useState, useCallback, useEffect, useMemo } from "react";
import { Box, Button, Flex, IconButton, TabNav } from "@radix-ui/themes";
import { Loader2, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import "./settings-dialog.css";

import {
  SettingsSidebar,
  type SettingsCategory,
} from "../components/settings-sidebar";
import { GeneralSettings } from "../components/general-settings";
import { ConnectionsSettings } from "../components/connections-settings";
import { ModelsSettings } from "../components/models-settings";
import { IndexSettings } from "../components/index-settings";
import { AgentToolsSettings } from "../components/agent-tools-settings";
import { AgentDefinitionsSettings } from "../components/agent-definitions-settings";
import { RulesSettings } from "../components/rules-settings";
import { SkillsSettings } from "../components/skills-settings";
import { fetchAgentTools, fetchSettings, updateSettings } from "../lib/settings-api";
import type { Settings, SettingsUpdateRequest } from "../lib/settings.types";
import {
  DEFAULT_MODEL_SETTINGS_TAB,
  DEFAULT_SETTINGS_ROUTE_CATEGORY,
  type ModelSettingsTab,
} from "../lib/settings-route";
import {
  applyCodeFontFamily,
  applyFontFamily,
  loadConfiguredFonts,
} from "@/lib/font-utils";

interface SettingsContentProps {
  appearance: "light" | "dark";
  onClose: () => void;
}

const SETTINGS_CATEGORIES: SettingsCategory[] = [
  "general",
  "connections",
  "models",
  "index",
  "agent-tools",
  "rules",
  "skills",
  "agents",
];

const CATEGORY_TITLE_KEY_MAP: Record<SettingsCategory, string> = {
  general: "settings.general",
  connections: "settings.connections",
  models: "settings.models",
  index: "settings.index",
  "agent-tools": "settings.agentTools",
  rules: "settings.rules",
  skills: "settings.skills",
  agents: "settings.agents",
};

export function SettingsContent({ appearance, onClose }: SettingsContentProps) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [activeCategory, setActiveCategory] = useState<SettingsCategory>(
    DEFAULT_SETTINGS_ROUTE_CATEGORY
  );
  const [activeModelTab, setActiveModelTab] = useState<ModelSettingsTab>(
    DEFAULT_MODEL_SETTINGS_TAB
  );

  const [editedSettings, setEditedSettings] = useState<Partial<Settings>>({});
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);

  const { data: serverSettings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });

  const {
    data: agentTools = [],
    isLoading: isAgentToolsLoading,
    error: agentToolsError,
  } = useQuery({
    queryKey: ["agent-tools"],
    queryFn: fetchAgentTools,
    staleTime: 5 * 60 * 1000,
  });

  const isCategoryLoading =
    isLoading || (activeCategory === "agent-tools" && isAgentToolsLoading);

  const agentToolsErrorMessage = useMemo(() => {
    if (!agentToolsError) return undefined;
    if (axios.isAxiosError(agentToolsError)) {
      const detail = agentToolsError.response?.data;
      if (typeof detail === "string") return detail;
      if (detail && typeof detail === "object" && "detail" in detail)
        return String(detail.detail);
      return agentToolsError.message;
    }
    if (agentToolsError instanceof Error) return agentToolsError.message;
    return t("settings.agentToolsLoadFailed");
  }, [agentToolsError, t]);

  useEffect(() => {
    if (serverSettings?.fontFamily) applyFontFamily(serverSettings.fontFamily);
    if (serverSettings?.codeFontFamily) applyCodeFontFamily(serverSettings.codeFontFamily);
  }, [serverSettings?.fontFamily, serverSettings?.codeFontFamily]);

  useEffect(() => {
    function handleResize() {
      setIsMobile(window.innerWidth < 768);
    }

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const displaySettings = useMemo<Settings | null>(() => {
    if (!serverSettings) return null;
    return {
      ...serverSettings,
      ...editedSettings,
      language: (editedSettings.language ?? i18n.language) as Settings["language"],
      theme: editedSettings.theme ?? appearance,
    };
  }, [serverSettings, editedSettings, i18n.language, appearance]);

  const hasChanges = useMemo(() => {
    if (!serverSettings) return false;
    const hasLocalEdits = Object.keys(editedSettings).length > 0;
    const languageChanged = i18n.language !== serverSettings.language;
    const themeChanged = appearance !== serverSettings.theme;
    return hasLocalEdits || languageChanged || themeChanged;
  }, [serverSettings, editedSettings, i18n.language, appearance]);

  const saveMutation = useMutation({
    mutationFn: async (settings: Settings) => {
      const request: SettingsUpdateRequest = {
        language: settings.language,
        theme: settings.theme,
        font_family: settings.fontFamily,
        code_font_family: settings.codeFontFamily,
        agent_tool_permissions: settings.agentToolPermissions.map((item) => ({
          tool_name: item.toolName,
          mode: item.mode,
        })),
      };
      return updateSettings(request);
    },
    onSuccess: (savedSettings) => {
      queryClient.setQueryData(["settings"], savedSettings);
      setEditedSettings({});
    },
  });

  const handleSettingsChange = useCallback((newSettings: Settings) => {
    applyFontFamily(newSettings.fontFamily);
    applyCodeFontFamily(newSettings.codeFontFamily);
    void loadConfiguredFonts(newSettings.fontFamily, newSettings.codeFontFamily);
    setEditedSettings(newSettings);
  }, []);

  const handleSave = useCallback(() => {
    if (displaySettings) saveMutation.mutate(displaySettings);
  }, [displaySettings, saveMutation]);

  const shouldShowSaveButton =
    ((activeCategory === "general" && !isCategoryLoading) ||
      (activeCategory === "agent-tools" && !isAgentToolsLoading));

  return (
    <Flex className="settings-dialog-layout">
      {!isMobile ? (
        <Box className="settings-dialog-sidebar-shell">
          <SettingsSidebar
            activeCategory={activeCategory}
            onCategoryChange={setActiveCategory}
          />
        </Box>
      ) : null}

      <Flex direction="column" className="settings-dialog-main">
        <IconButton
          className="settings-dialog-main-close"
          variant="ghost"
          color="gray"
          radius="full"
          aria-label={t("common.close")}
          onClick={onClose}
        >
          <X size={18} />
        </IconButton>

        {isMobile ? (
          <Box className="settings-dialog-mobile-tabs-row">
            <Box className="settings-dialog-mobile-tabs-scroll">
              <TabNav.Root size="2" color="gray" highContrast>
                {SETTINGS_CATEGORIES.map((category) => (
                  <TabNav.Link key={category} asChild active={activeCategory === category}>
                    <button
                      type="button"
                      className="settings-dialog-mobile-tab-button"
                      onClick={() => setActiveCategory(category)}
                    >
                      {t(CATEGORY_TITLE_KEY_MAP[category])}
                    </button>
                  </TabNav.Link>
                ))}
              </TabNav.Root>
            </Box>
          </Box>
        ) : null}

          <Box className="settings-dialog-body">
          <Box className={activeCategory === "agents" || activeCategory === "skills" || activeCategory === "rules" ? "settings-dialog-content-scroll settings-dialog-content-scroll--split-panel" : "settings-dialog-content-scroll"}>
            {isCategoryLoading ? (
              <Flex align="center" justify="center" className="settings-dialog-loading-state">
                <Loader2 size={24} className="animate-spin" />
              </Flex>
            ) : displaySettings ? (
              <>
                {activeCategory === "general" ? (
                  <GeneralSettings
                    settings={displaySettings}
                    onSettingsChange={handleSettingsChange}
                  />
                ) : null}
                {activeCategory === "connections" ? <ConnectionsSettings /> : null}
                {activeCategory === "models" ? (
                  <ModelsSettings
                    activeTab={activeModelTab}
                    onActiveTabChange={setActiveModelTab}
                  />
                ) : null}
                {activeCategory === "index" ? <IndexSettings /> : null}
                {activeCategory === "agent-tools" ? (
                  <AgentToolsSettings
                    settings={displaySettings}
                    tools={agentTools}
                    errorMessage={agentToolsErrorMessage}
                    onSettingsChange={handleSettingsChange}
                  />
                ) : null}
                {activeCategory === "rules" ? <RulesSettings /> : null}
                {activeCategory === "skills" ? <SkillsSettings variant="settings" /> : null}
                {activeCategory === "agents" ? (
                  <AgentDefinitionsSettings onCloseSettings={onClose} />
                ) : null}
              </>
            ) : null}
          </Box>

          {shouldShowSaveButton ? (
            <Box className="settings-dialog-savebar">
              <Button
                size="3"
                disabled={!hasChanges || saveMutation.isPending}
                onClick={handleSave}
              >
                {saveMutation.isPending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : null}
                {t("settings.save")}
              </Button>
            </Box>
          ) : null}
        </Box>
      </Flex>
    </Flex>
  );
}
