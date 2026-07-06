import { Box, Flex } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpenText,
  ChartNoAxesCombined,
  Globe,
  LibraryBig,
  UserRound,
  Workflow,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate, useParams } from "react-router";

import { saveLanguagePreference, supportedLanguages, type LanguageCode } from "@/i18n";
import { apiClient, fetchProject } from "@/lib/api-client";

import { useAppShell } from "./app-shell-context";
import {
  SIDEBAR_COLLAPSED_WIDTH,
  SIDEBAR_EXPANDED_WIDTH,
  type AppSidebarNavItem,
} from "./app-sidebar.constants";
import { SidebarActions } from "./sidebar-actions";
import { SidebarBrand } from "./sidebar-brand";
import { SidebarNav } from "./sidebar-nav";

const MotionBox = motion.create(Box);
const MotionFlex = motion.create(Flex);

interface AppSidebarProps {
  appearance: "light" | "dark";
  onToggleTheme: () => void;
}

export function AppSidebar({ appearance, onToggleTheme }: AppSidebarProps) {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { projectId } = useParams<{ projectId: string }>();
  const { isMobile, isSidebarOpen, closeSidebar, openSettings } = useAppShell();

  const [isExpanded, setIsExpanded] = useState(false);
  const [isLogoHovered, setIsLogoHovered] = useState(false);
  const [shouldAnimateTheme, setShouldAnimateTheme] = useState(false);
  const logoPointerInsideRef = useRef(false);
  const prevAppearanceRef = useRef(appearance);
  const prevPathnameRef = useRef(location.pathname);

  const sidebarWidth = isMobile
    ? SIDEBAR_EXPANDED_WIDTH
    : isExpanded
      ? SIDEBAR_EXPANDED_WIDTH
      : SIDEBAR_COLLAPSED_WIDTH;

  useEffect(() => {
    document.documentElement.style.setProperty(
      "--app-sidebar-width",
      `${isMobile ? 0 : sidebarWidth}px`,
    );
  }, [isMobile, sidebarWidth]);

  useEffect(() => {
    if (isMobile && isSidebarOpen && prevPathnameRef.current !== location.pathname) {
      closeSidebar();
    }

    prevPathnameRef.current = location.pathname;
  }, [closeSidebar, isMobile, isSidebarOpen, location.pathname]);

  useEffect(() => {
    if (prevAppearanceRef.current !== appearance && shouldAnimateTheme) {
      const timer = setTimeout(() => {
        setShouldAnimateTheme(false);
      }, 300);
      return () => clearTimeout(timer);
    }
    prevAppearanceRef.current = appearance;
  }, [appearance, shouldAnimateTheme]);

  const { data: currentProject } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => fetchProject(projectId!),
    enabled: !!projectId,
  });

  const navItems = useMemo<AppSidebarNavItem[]>(() => {
    const pathname = location.pathname;
    const items: AppSidebarNavItem[] = [
      {
        label: t("topbar.projects"),
        href: "/",
        icon: LibraryBig,
        active: pathname === "/",
      },
      {
        label: t("topbar.workspace"),
        href: "/world-info",
        icon: Globe,
        active: pathname.startsWith("/world-info"),
      },
      {
        label: t("topbar.characters"),
        href: "/characters",
        icon: UserRound,
        active: pathname.startsWith("/characters"),
      },
      {
        label: t("topbar.promptChains"),
        href: "/prompt-chains",
        icon: Workflow,
        active: pathname.startsWith("/prompt-chains"),
      },
      {
        label: t("dashboard.title"),
        href: "/dashboard",
        icon: ChartNoAxesCombined,
        active: pathname.startsWith("/dashboard"),
      },
    ];

    if (projectId) {
      items.push({
        label: t("topbar.editor"),
        href: `/projects/${projectId}`,
        icon: BookOpenText,
        active: pathname.startsWith(`/projects/${projectId}`),
      });
    }

    return items;
  }, [location.pathname, projectId, t]);

  const handleLanguageChange = async (language: string) => {
    const nextLanguage = language as LanguageCode;
    i18n.changeLanguage(nextLanguage);
    saveLanguagePreference(nextLanguage);

    try {
      await apiClient.put("/settings", { language: nextLanguage });
    } catch (error) {
      console.error("Failed to sync language setting to server:", error);
    }
  };

  const handleThemeToggle = useCallback(() => {
    setShouldAnimateTheme(true);
    onToggleTheme();
  }, [onToggleTheme]);

  const toggleExpanded = useCallback(() => {
    if (isMobile) {
      closeSidebar();
      return;
    }

    logoPointerInsideRef.current = false;
    setIsLogoHovered(false);
    setIsExpanded((prev) => !prev);
  }, [closeSidebar, isMobile]);

  const handleLogoPointerEnter = useCallback(() => {
    logoPointerInsideRef.current = true;
    if (!isExpanded) {
      setIsLogoHovered(true);
    }
  }, [isExpanded]);

  const handleLogoPointerLeave = useCallback(() => {
    logoPointerInsideRef.current = false;
    setIsLogoHovered(false);
  }, []);

  const handleLogoPointerMove = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      if (!isExpanded && logoPointerInsideRef.current) {
        const { left, right, top, bottom } = event.currentTarget.getBoundingClientRect();
        const isInside =
          event.clientX >= left &&
          event.clientX <= right &&
          event.clientY >= top &&
          event.clientY <= bottom;

        if (isInside && !isLogoHovered) {
          setIsLogoHovered(true);
        }
      }
    },
    [isExpanded, isLogoHovered],
  );

  const navigateToProjects = useCallback(() => {
    navigate("/");
  }, [navigate]);

  const handleOpenSettings = useCallback(() => {
    if (isMobile) {
      closeSidebar();
    }
    openSettings();
  }, [closeSidebar, isMobile, openSettings]);

  return (
    <>
      <AnimatePresence initial={false}>
        {isMobile && isSidebarOpen && (
          <motion.div
            key="mobile-sidebar-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0, 0, 0, 0.36)",
              zIndex: 99,
            }}
            onClick={closeSidebar}
          />
        )}
      </AnimatePresence>

      <AnimatePresence initial={false}>
        {(!isMobile || isSidebarOpen) && (
          <MotionBox
            key={isMobile ? "mobile-sidebar" : "desktop-sidebar"}
            position="fixed"
            top="0"
            left="0"
            bottom="var(--app-status-bar-height)"
            initial={isMobile ? { x: -SIDEBAR_EXPANDED_WIDTH } : false}
            animate={
              isMobile ? { x: 0, width: SIDEBAR_EXPANDED_WIDTH } : { x: 0, width: sidebarWidth }
            }
            exit={isMobile ? { x: -SIDEBAR_EXPANDED_WIDTH } : undefined}
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
            style={{
              borderRight: "1px solid var(--gray-a5)",
              background: "color-mix(in srgb, var(--color-background) 92%, transparent)",
              backdropFilter: "blur(12px)",
              zIndex: 100,
              overflow: "hidden",
              boxShadow: isMobile ? "var(--shadow-5)" : undefined,
            }}
          >
            <Flex
              direction="column"
              height="100%"
              p="3"
            >
              <SidebarBrand
                title={currentProject?.title ?? t("common.appName")}
                isExpanded={isMobile || isExpanded}
                isHovered={isLogoHovered}
                expandLabel={t("topbar.expand")}
                projectsLabel={t("topbar.projects")}
                collapseLabel={t("topbar.collapse")}
                onToggleExpanded={toggleExpanded}
                onNavigateHome={navigateToProjects}
                onPointerEnter={handleLogoPointerEnter}
                onPointerLeave={handleLogoPointerLeave}
                onPointerMove={handleLogoPointerMove}
              />

              <Box
                style={{
                  width: "100%",
                  height: 13,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "flex-start",
                  margin: "6px 0",
                  flexShrink: 0,
                }}
              >
                <MotionBox
                  initial={false}
                  animate={{
                    width: isMobile || isExpanded ? SIDEBAR_EXPANDED_WIDTH - 40 : 32,
                    marginLeft: isMobile || isExpanded ? 8 : 4,
                  }}
                  transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                  style={{
                    height: 1,
                    background: "var(--gray-a5)",
                  }}
                />
              </Box>

              <SidebarNav
                items={navItems}
                isExpanded={isMobile || isExpanded}
              />

              <MotionFlex
                layout
                mt="auto"
                direction={isMobile || isExpanded ? "row" : "column"}
                align="center"
                justify={isMobile || isExpanded ? "end" : "center"}
                gap="1"
                width="100%"
                transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
              >
                <SidebarActions
                  appearance={appearance}
                  isExpanded={isMobile || isExpanded}
                  shouldAnimateTheme={shouldAnimateTheme}
                  languageLabel={t("topbar.language")}
                  settingsLabel={t("topbar.settings")}
                  toggleThemeLabel={t("topbar.toggleTheme")}
                  themeTooltip={
                    appearance === "light"
                      ? t("topbar.toggleDarkMode")
                      : t("topbar.toggleLightMode")
                  }
                  languages={supportedLanguages.map((lang) => ({
                    code: lang.code,
                    name: lang.name,
                  }))}
                  currentLanguage={i18n.language}
                  onLanguageChange={handleLanguageChange}
                  onToggleTheme={handleThemeToggle}
                  onOpenSettings={handleOpenSettings}
                />
              </MotionFlex>
            </Flex>
          </MotionBox>
        )}
      </AnimatePresence>
    </>
  );
}
