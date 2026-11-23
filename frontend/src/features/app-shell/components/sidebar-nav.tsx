import { Box, Flex, Text, Tooltip } from "@radix-ui/themes";
import { motion } from "motion/react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import "./sidebar-nav.css";
import {
  SIDEBAR_ICON_SIZE,
  SIDEBAR_EXPANDED_WIDTH,
  SIDEBAR_ITEM_HEIGHT,
  type AppSidebarNavItem,
} from "./app-sidebar.constants";

const MotionFlex = motion.create(Flex);
const MotionBox = motion.create(Box);

interface SidebarNavProps {
  items: AppSidebarNavItem[];
  isExpanded: boolean;
  onNavigate?: () => void;
}

export function SidebarDivider({
  isExpanded,
  inPopover = false,
}: {
  isExpanded: boolean;
  inPopover?: boolean;
}) {
  return (
    <Box
      className="app-sidebar-divider"
      data-popover={inPopover || undefined}
      aria-hidden="true"
    >
      <MotionBox
        className="app-sidebar-divider__line"
        initial={false}
        animate={{
          width: inPopover ? "calc(100% - 16px)" : isExpanded ? SIDEBAR_EXPANDED_WIDTH - 40 : 32,
          marginLeft: isExpanded ? 8 : 4,
        }}
        transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
      />
    </Box>
  );
}

interface SidebarNavItemProps extends Omit<AppSidebarNavItem, "icon"> {
  icon: ReactNode;
  isExpanded: boolean;
  onNavigate?: () => void;
}

export function SidebarNavItem({
  href,
  label,
  active,
  icon,
  isExpanded,
  onNavigate,
}: SidebarNavItemProps) {
  const content = (
    <MotionFlex
      align="center"
      className="app-sidebar-nav-item"
      data-active={active ? "true" : "false"}
      style={{
        display: "flex",
        alignItems: "center",
        height: SIDEBAR_ITEM_HEIGHT,
      }}
      whileTap={{ scale: 0.97 }}
      transition={{ duration: 0.15 }}
    >
      <Box
        className="app-sidebar-nav-item__icon-box"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: SIDEBAR_ITEM_HEIGHT,
          height: SIDEBAR_ITEM_HEIGHT,
          flexShrink: 0,
        }}
      >
        {icon}
      </Box>
      <motion.div
        initial={false}
        animate={{
          opacity: isExpanded ? 1 : 0,
          width: isExpanded ? 132 : 0,
        }}
        transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
        className="app-sidebar-nav-item__label"
        style={{ pointerEvents: isExpanded ? "auto" : "none" }}
      >
        <Text
          size="2"
          weight={active ? "bold" : "medium"}
        >
          {label}
        </Text>
      </motion.div>
    </MotionFlex>
  );

  const linked = (
    <Link
      to={href}
      aria-label={label}
      aria-current={active ? "page" : undefined}
      className="app-sidebar-nav-link"
      style={{ display: "block", width: "100%" }}
      onClick={onNavigate}
    >
      {content}
    </Link>
  );

  return isExpanded ? (
    <Box width="100%">{linked}</Box>
  ) : (
    <Tooltip
      content={label}
      side="right"
    >
      <Box width="100%">{linked}</Box>
    </Tooltip>
  );
}

export function SidebarNav({ items, isExpanded, onNavigate }: SidebarNavProps) {
  return (
    <Flex
      direction="column"
      align="center"
      gap="1"
      width="100%"
    >
      {items.map(({ icon: Icon, ...item }) => (
        <SidebarNavItem
          key={item.href}
          {...item}
          icon={
            <Icon
              size={SIDEBAR_ICON_SIZE}
              color="currentColor"
              className="app-sidebar-nav-item__icon"
            />
          }
          isExpanded={isExpanded}
          onNavigate={onNavigate}
        />
      ))}
    </Flex>
  );
}
