/**
 * MacroSidebar - 宏侧边栏主容器
 *
 * 根据选中的宏类型渲染对应的编辑/预览面板。
 */

import { Box, Text, Heading } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";

import type { MacroNode } from "@/lib/macro";

import { EmptyPanel } from "./empty-panel";
import { EndIfPanel } from "./endif-panel";
import { GetlistPanel } from "./getlist-panel";
import { GetmemPanel } from "./getmem-panel";
import { GetworldPanel } from "./getworld-panel";
import { IfPanel } from "./if-panel";

interface MacroSidebarProps {
  selectedMacro: MacroNode | null;
  onMacroUpdate?: (macroRaw: string) => void;
  workDir?: {
    projectId: string | null;
    chapterId: string | null;
  };
}

export function MacroSidebar({ selectedMacro, onMacroUpdate, workDir }: MacroSidebarProps) {
  const { t } = useTranslation();

  const renderPanel = () => {
    if (!selectedMacro) {
      return <EmptyPanel />;
    }

    switch (selectedMacro.name) {
      case "getmem":
        return (
          <GetmemPanel
            macro={selectedMacro}
            workDir={workDir}
          />
        );
      case "getlist":
        return <GetlistPanel />;
      case "getworld":
        return <GetworldPanel />;
      case "if":
        return (
          <IfPanel
            macro={selectedMacro}
            onUpdate={onMacroUpdate}
          />
        );
      case "endif":
        return <EndIfPanel />;
      default:
        return <EmptyPanel />;
    }
  };

  return (
    <Box
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <Box
        p="3"
        style={{
          borderBottom: "1px solid var(--gray-a5)",
          flexShrink: 0,
        }}
      >
        <Heading
          size="3"
          weight="medium"
        >
          {t("promptChains.macroPanel")}
        </Heading>
        {selectedMacro && (
          <Text
            size="2"
            color="gray"
          >
            {selectedMacro.name}
          </Text>
        )}
      </Box>

      <Box
        p="3"
        style={{
          flex: 1,
          overflowY: "auto",
        }}
      >
        {renderPanel()}
      </Box>
    </Box>
  );
}
