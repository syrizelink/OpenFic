import { Box, Dialog, Flex, TabNav } from "@radix-ui/themes";
import { BookOpenText, Layers3, Sparkles } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import "./summary-panel.css";

import { ChapterSummaryListView } from "./summary-panel-chapter-list";
import { LongTermSummaryListView } from "./summary-panel-long-term-list";
import { SummaryMaintenanceView } from "./summary-panel-maintenance";

interface SummaryPanelProps {
  projectId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trigger?: React.ReactNode;
}

type SummarySection = "chapters" | "long-term" | "maintenance";

interface SummaryTabItem {
  section: SummarySection;
  icon: React.ReactNode;
  label: string;
}

function SummaryNavButton({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="summary-nav-item"
      data-active={active ? "true" : "false"}
    >
      <Flex
        align="center"
        gap="2"
      >
        <Box className="summary-nav-item__icon">{icon}</Box>
        {label}
      </Flex>
    </button>
  );
}

export function SummaryPanel({ projectId, open, onOpenChange, trigger }: SummaryPanelProps) {
  const { t } = useTranslation();
  const [section, setSection] = useState<SummarySection>("chapters");
  const summaryTabs: SummaryTabItem[] = [
    { section: "chapters", icon: <BookOpenText size={16} />, label: t("summary.tabs.chapters") },
    { section: "long-term", icon: <Layers3 size={17} />, label: t("summary.tabs.ranges") },
    { section: "maintenance", icon: <Sparkles size={17} />, label: t("summary.tabs.generate") },
  ];

  return (
    <Dialog.Root
      open={open}
      onOpenChange={onOpenChange}
    >
      {trigger && <Dialog.Trigger>{trigger}</Dialog.Trigger>}
      <Dialog.Content
        className="summary-panel-content"
        maxWidth="1180px"
        style={{ width: "min(1180px, calc(100vw - 32px))" }}
      >
        <Dialog.Title className="summary-panel-visually-hidden">{t("summary.title")}</Dialog.Title>
        <Dialog.Description className="summary-panel-visually-hidden">
          {t("summary.description")}
        </Dialog.Description>
        <Flex className="summary-panel-layout">
          <Box
            p="3"
            className="summary-panel-sidebar"
          >
            <Flex
              direction="column"
              gap="1"
              height="100%"
            >
              {summaryTabs.map((tab) => (
                <SummaryNavButton
                  key={tab.section}
                  active={section === tab.section}
                  icon={tab.icon}
                  label={tab.label}
                  onClick={() => setSection(tab.section)}
                />
              ))}
            </Flex>
          </Box>

          <Box
            px="5"
            pt="3"
            className="summary-panel-tabs"
          >
            <TabNav.Root
              size="2"
              color="gray"
              highContrast
            >
              {summaryTabs.map((tab) => (
                <TabNav.Link
                  key={tab.section}
                  asChild
                  active={section === tab.section}
                >
                  <button
                    type="button"
                    className="summary-tab-button"
                    onClick={() => setSection(tab.section)}
                  >
                    <Box className="summary-tab-button__icon">{tab.icon}</Box>
                    {tab.label}
                  </button>
                </TabNav.Link>
              ))}
            </TabNav.Root>
          </Box>

          <Flex
            direction="column"
            flexGrow="1"
            className="summary-panel-main"
          >
            <Box
              p="5"
              className="summary-panel-body"
            >
              {section === "chapters" && (
                <ChapterSummaryListView
                  key={`${projectId}-${open ? "open" : "closed"}`}
                  projectId={projectId}
                />
              )}

              {section === "long-term" && (
                <LongTermSummaryListView
                  projectId={projectId}
                  open={open}
                  emptyText={t("summary.emptyRanges")}
                />
              )}

              {section === "maintenance" && <SummaryMaintenanceView projectId={projectId} />}
            </Box>
          </Flex>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
