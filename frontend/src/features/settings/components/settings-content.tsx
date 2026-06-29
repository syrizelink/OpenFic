import { useState, useCallback, useEffect, useMemo } from "react";
import { Box, Button, Flex, IconButton, Text } from "@radix-ui/themes";
import { ChevronLeft, ChevronRight, Loader2, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import axios from "axios";
import "./settings-dialog.css";

import { SettingsSidebar } from "../components/settings-sidebar";
import { SETTINGS_CATEGORY_ITEMS, type SettingsCategory } from "../lib/settings-categories";
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

const MotionBox = motion.create(Box);

type MobileSubpage = "list" | "detail";

const mobilePageVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? "100%" : "-100%",
  }),
  center: {
    x: 0,
  },
  exit: (direction: number) => ({
    x: direction > 0 ? "-100%" : "100%",
  }),
};

interface SettingsContentProps {
  appearance: "light" | "dark";
  onClose: () => void;
  route?: {
    category: SettingsCategory;
    modelTab?: ModelSettingsTab;
  };
}

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

export function SettingsContent({ appearance, onClose, route }: SettingsContentProps) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const initialCategory = route?.category ?? DEFAULT_SETTINGS_ROUTE_CATEGORY;
  const [activeCategory, setActiveCategory] = useState<SettingsCategory>(initialCategory);
  const [activeModelTab, setActiveModelTab] = useState<ModelSettingsTab>(
    route?.category === "models"
      ? (route.modelTab ?? DEFAULT_MODEL_SETTINGS_TAB)
      : DEFAULT_MODEL_SETTINGS_TAB
  );
  const [mobileView, setMobileView] = useState<"list" | "detail">(
    route ? "detail" : "list"
  );
  const [mobileSubpage, setMobileSubpage] = useState<MobileSubpage>("list");
  const [mobileSubpageTitle, setMobileSubpageTitle] = useState<string | null>(null);
  const [mobileDirection, setMobileDirection] = useState<1 | -1>(1);

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
  const isSplitPanelCategory =
    activeCategory === "agents" || activeCategory === "skills" || activeCategory === "rules";
  const shouldUseFormPagePadding =
    activeCategory === "general"
    || activeCategory === "connections"
    || activeCategory === "models"
    || activeCategory === "index"
    || activeCategory === "agent-tools";
  const isMobileListView = isMobile && mobileView === "list";
  const isMobileSubpageDetail =
    isMobile && mobileView === "detail" && isSplitPanelCategory && mobileSubpage === "detail";
  const mobileTitle = isMobileListView
    ? t("topbar.settings")
    : isMobileSubpageDetail && mobileSubpageTitle
      ? mobileSubpageTitle
      : t(CATEGORY_TITLE_KEY_MAP[activeCategory]);

  const handleMobileCategorySelect = useCallback((category: SettingsCategory) => {
    setMobileDirection(1);
    setActiveCategory(category);
    setMobileSubpage("list");
    setMobileSubpageTitle(null);
    setMobileView("detail");
  }, []);

  const handleMobileBack = useCallback(() => {
    if (isMobileListView) {
      onClose();
      return;
    }

    if (isMobileSubpageDetail) {
      setMobileDirection(-1);
      setMobileSubpage("list");
      return;
    }

    setMobileDirection(-1);
    setMobileView("list");
  }, [isMobileListView, isMobileSubpageDetail, onClose]);

  const handleMobileSubpageChange = useCallback((page: MobileSubpage) => {
    setMobileDirection(page === "detail" ? 1 : -1);
    setMobileSubpage(page);
  }, []);

  const detailPageContent = (
    <>
      <Box
        className={isSplitPanelCategory
          ? "settings-dialog-content-scroll settings-dialog-content-scroll--split-panel"
          : shouldUseFormPagePadding
            ? "settings-dialog-content-scroll settings-dialog-content-scroll--form-page"
            : "settings-dialog-content-scroll"}
      >
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
            {activeCategory === "rules" ? (
              <RulesSettings
                mobilePage={mobileSubpage}
                mobileDirection={mobileDirection}
                onMobileDetailTitleChange={setMobileSubpageTitle}
                onMobilePageChange={handleMobileSubpageChange}
              />
            ) : null}
            {activeCategory === "skills" ? (
              <SkillsSettings
                variant="settings"
                mobilePage={mobileSubpage}
                mobileDirection={mobileDirection}
                onMobileDetailTitleChange={setMobileSubpageTitle}
                onMobilePageChange={handleMobileSubpageChange}
              />
            ) : null}
            {activeCategory === "agents" ? (
              <AgentDefinitionsSettings
                onCloseSettings={onClose}
                mobilePage={mobileSubpage}
                mobileDirection={mobileDirection}
                onMobileDetailTitleChange={setMobileSubpageTitle}
                onMobilePageChange={handleMobileSubpageChange}
              />
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
    </>
  );

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
        {isMobile ? (
          <Flex align="center" className="settings-dialog-mobile-topbar">
            <Flex align="center" gap="2" className="settings-dialog-mobile-topbar-leading">
              <IconButton
                variant="ghost"
                color="gray"
                radius="full"
                aria-label={t("common.back")}
                onClick={handleMobileBack}
              >
                  <ChevronLeft size={18} />
              </IconButton>
              <Text size="2" weight="medium" className="settings-dialog-mobile-topbar-title">
                {mobileTitle}
              </Text>
            </Flex>
            <Box className="settings-dialog-mobile-topbar-side settings-dialog-mobile-topbar-side--end">
              <IconButton
                variant="ghost"
                color="gray"
                radius="full"
                aria-label={t("common.close")}
                onClick={onClose}
              >
                <X size={18} />
              </IconButton>
            </Box>
          </Flex>
        ) : (
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
        )}

        <Box className="settings-dialog-body">
          {isMobile ? (
            <Box className="settings-dialog-mobile-page-stack">
              <AnimatePresence initial={false} custom={mobileDirection} mode="sync">
                {isMobileListView ? (
                  <MotionBox
                    key="settings-category-list"
                    custom={mobileDirection}
                    variants={mobilePageVariants}
                    initial="enter"
                    animate="center"
                    exit="exit"
                    transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                    className="settings-dialog-mobile-page"
                  >
                    <Box className="settings-dialog-mobile-category-list" role="list">
                      {SETTINGS_CATEGORY_ITEMS.map((category) => {
                        const Icon = category.icon;
                        return (
                          <button
                            key={category.id}
                            type="button"
                            className="settings-dialog-mobile-category-item"
                            onClick={() => handleMobileCategorySelect(category.id)}
                          >
                            <Flex align="center" gap="3" className="settings-dialog-mobile-category-item-content">
                              <span className="settings-dialog-mobile-category-item-icon" aria-hidden="true">
                                {Icon}
                              </span>
                              <Text size="2">{t(category.labelKey)}</Text>
                            </Flex>
                            <ChevronRight size={16} className="settings-dialog-mobile-category-item-arrow" />
                          </button>
                        );
                      })}
                    </Box>
                  </MotionBox>
                ) : (
                  <MotionBox
                    key={`settings-category-detail-${activeCategory}`}
                    custom={mobileDirection}
                    variants={mobilePageVariants}
                    initial="enter"
                    animate="center"
                    exit="exit"
                    transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                    className="settings-dialog-mobile-page"
                  >
                    {detailPageContent}
                  </MotionBox>
                )}
              </AnimatePresence>
            </Box>
          ) : (
            detailPageContent
          )}
        </Box>
      </Flex>
    </Flex>
  );
}
