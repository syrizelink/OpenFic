import type { LucideIcon } from "lucide-react";

export const SIDEBAR_COLLAPSED_WIDTH = 64;
export const SIDEBAR_EXPANDED_WIDTH = 232;
export const SIDEBAR_ITEM_HEIGHT = 40;
export const SIDEBAR_ICON_SIZE = 20;
export const SIDEBAR_ICON_ACTIVE_COLOR = "var(--gray-12)";

export const sidebarActionButtonStyle = {
  width: SIDEBAR_ITEM_HEIGHT,
  height: SIDEBAR_ITEM_HEIGHT,
  borderRadius: "var(--radius-3)",
} as const;

export interface AppSidebarNavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  active: boolean;
}
