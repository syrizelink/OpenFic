import { Box, Flex, Text, IconButton, Tooltip } from "@radix-ui/themes";
import { BookOpen, PanelLeft } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { KeyboardEvent, PointerEvent } from "react";
import {
  SIDEBAR_EXPANDED_WIDTH,
  SIDEBAR_ICON_ACTIVE_COLOR,
  SIDEBAR_ICON_COLOR,
  SIDEBAR_ICON_SIZE,
  SIDEBAR_ITEM_HEIGHT,
  sidebarActionButtonStyle,
} from "./app-sidebar.constants";

const MotionFlex = motion.create(Flex);

interface SidebarBrandProps {
  title: string;
  isExpanded: boolean;
  isHovered: boolean;
  expandLabel: string;
  projectsLabel: string;
  collapseLabel: string;
  onToggleExpanded: () => void;
  onNavigateHome: () => void;
  onPointerEnter: () => void;
  onPointerLeave: () => void;
  onPointerMove: (event: PointerEvent<HTMLDivElement>) => void;
}

export function SidebarBrand({
  title,
  isExpanded,
  isHovered,
  expandLabel,
  projectsLabel,
  collapseLabel,
  onToggleExpanded,
  onNavigateHome,
  onPointerEnter,
  onPointerLeave,
  onPointerMove,
}: SidebarBrandProps) {
  const handleActivate = () => {
    if (isExpanded) {
      onNavigateHome();
    } else {
      onToggleExpanded();
    }
  };

  return (
    <Flex align="center" gap="0" style={{ height: SIDEBAR_ITEM_HEIGHT, flexShrink: 0 }}>
      <MotionFlex
        align="center"
        onPointerEnter={onPointerEnter}
        onPointerLeave={onPointerLeave}
        onPointerMove={onPointerMove}
        onClick={handleActivate}
        role="button"
        tabIndex={0}
        aria-label={isExpanded ? projectsLabel : expandLabel}
        onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            handleActivate();
          }
        }}
        style={{
          minWidth: SIDEBAR_ITEM_HEIGHT,
          height: SIDEBAR_ITEM_HEIGHT,
          width: isExpanded ? SIDEBAR_EXPANDED_WIDTH - 72 : SIDEBAR_ITEM_HEIGHT,
          cursor: "pointer",
          borderRadius: "var(--radius-3)",
          backgroundColor: !isExpanded && isHovered ? "var(--gray-a3)" : "transparent",
          justifyContent: "flex-start",
          overflow: "hidden",
        }}
        animate={{
          width: isExpanded ? SIDEBAR_EXPANDED_WIDTH - 72 : SIDEBAR_ITEM_HEIGHT,
        }}
        transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
        whileTap={{ scale: 0.97 }}
      >
        <Box
          style={{
            width: SIDEBAR_ITEM_HEIGHT,
            height: SIDEBAR_ITEM_HEIGHT,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <AnimatePresence mode="wait" initial={false}>
            {!isExpanded && isHovered ? (
              <motion.div
                key="panel"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.1 }}
                style={{ display: "flex" }}
              >
                <PanelLeft
                  size={SIDEBAR_ICON_SIZE}
                  color="currentColor"
                  style={{ color: SIDEBAR_ICON_ACTIVE_COLOR }}
                />
              </motion.div>
            ) : (
              <motion.div
                key="logo"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.1 }}
                style={{ display: "flex" }}
              >
                <BookOpen
                  size={SIDEBAR_ICON_SIZE}
                  color="currentColor"
                  style={{ color: SIDEBAR_ICON_COLOR }}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </Box>

        <AnimatePresence initial={false}>
          {isExpanded && (
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: 116 }}
              exit={{ opacity: 0, width: 0 }}
              transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
              style={{ minWidth: 0, overflow: "hidden" }}
            >
              <Text
                size="3"
                weight="bold"
                style={{
                  display: "block",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  maxWidth: 116,
                }}
              >
                {title}
              </Text>
            </motion.div>
          )}
        </AnimatePresence>
      </MotionFlex>

      {isExpanded && (
        <Box ml="auto" style={{ flexShrink: 0 }}>
          <Tooltip content={collapseLabel}>
            <IconButton
              variant="ghost"
              size="2"
              onClick={onToggleExpanded}
              aria-label={collapseLabel}
              style={{ ...sidebarActionButtonStyle, cursor: "pointer" }}
            >
              <PanelLeft size={SIDEBAR_ICON_SIZE} color="currentColor" />
            </IconButton>
          </Tooltip>
        </Box>
      )}
    </Flex>
  );
}
