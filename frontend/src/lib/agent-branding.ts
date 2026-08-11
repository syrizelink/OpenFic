/**
 * Agent Branding
 *
 * 主智能体颜色与 Icon 的预定义列表及工具函数。
 * 颜色键对应 Radix 主题色，Icon 键对应 lucide 图标。
 */

import type { LucideIcon } from "lucide-react";
import {
  Anchor,
  Bell,
  Blocks,
  BookOpen,
  Camera,
  Cloud,
  Compass,
  Crown,
  Feather,
  Flame,
  Gem,
  Globe,
  GraduationCap,
  Heart,
  Key,
  Lightbulb,
  ListChecks,
  Map,
  Moon,
  Music,
  Palette,
  PenTool,
  Puzzle,
  Rocket,
  Shield,
  Sparkles,
  Star,
  Target,
  Wand2,
  Zap,
} from "lucide-react";

import i18n from "@/i18n";

export interface AgentBrandingOption {
  value: string;
  labelKey: string;
}

export const AGENT_COLOR_OPTIONS: AgentBrandingOption[] = [
  { value: "blue", labelKey: "agentBranding.color.blue" },
  { value: "green", labelKey: "agentBranding.color.green" },
  { value: "orange", labelKey: "agentBranding.color.orange" },
  { value: "purple", labelKey: "agentBranding.color.purple" },
  { value: "teal", labelKey: "agentBranding.color.teal" },
  { value: "red", labelKey: "agentBranding.color.red" },
  { value: "amber", labelKey: "agentBranding.color.amber" },
  { value: "pink", labelKey: "agentBranding.color.pink" },
  { value: "indigo", labelKey: "agentBranding.color.indigo" },
  { value: "cyan", labelKey: "agentBranding.color.cyan" },
  { value: "lime", labelKey: "agentBranding.color.lime" },
  { value: "violet", labelKey: "agentBranding.color.violet" },
  { value: "bronze", labelKey: "agentBranding.color.bronze" },
  { value: "gray", labelKey: "agentBranding.color.gray" },
];

export interface AgentIconOption extends AgentBrandingOption {
  icon: LucideIcon;
}

export const AGENT_ICON_OPTIONS: AgentIconOption[] = [
  { value: "bot", labelKey: "agentBranding.icon.bot", icon: GraduationCap },
  { value: "sparkles", labelKey: "agentBranding.icon.sparkles", icon: Sparkles },
  { value: "pen-tool", labelKey: "agentBranding.icon.penTool", icon: PenTool },
  { value: "wand", labelKey: "agentBranding.icon.wand", icon: Wand2 },
  { value: "compass", labelKey: "agentBranding.icon.compass", icon: Compass },
  { value: "crown", labelKey: "agentBranding.icon.crown", icon: Crown },
  { value: "rocket", labelKey: "agentBranding.icon.rocket", icon: Rocket },
  { value: "shield", labelKey: "agentBranding.icon.shield", icon: Shield },
  { value: "star", labelKey: "agentBranding.icon.star", icon: Star },
  { value: "lightbulb", labelKey: "agentBranding.icon.lightbulb", icon: Lightbulb },
  { value: "target", labelKey: "agentBranding.icon.target", icon: Target },
  { value: "zap", labelKey: "agentBranding.icon.zap", icon: Zap },
  { value: "book-open", labelKey: "agentBranding.icon.bookOpen", icon: BookOpen },
  { value: "list-checks", labelKey: "agentBranding.icon.listChecks", icon: ListChecks },
  { value: "feather", labelKey: "agentBranding.icon.feather", icon: Feather },
  { value: "palette", labelKey: "agentBranding.icon.palette", icon: Palette },
  { value: "blocks", labelKey: "agentBranding.icon.blocks", icon: Blocks },
  { value: "gem", labelKey: "agentBranding.icon.gem", icon: Gem },
  { value: "key", labelKey: "agentBranding.icon.key", icon: Key },
  { value: "globe", labelKey: "agentBranding.icon.globe", icon: Globe },
  { value: "map", labelKey: "agentBranding.icon.map", icon: Map },
  { value: "music", labelKey: "agentBranding.icon.music", icon: Music },
  { value: "camera", labelKey: "agentBranding.icon.camera", icon: Camera },
  { value: "heart", labelKey: "agentBranding.icon.heart", icon: Heart },
  { value: "flame", labelKey: "agentBranding.icon.flame", icon: Flame },
  { value: "anchor", labelKey: "agentBranding.icon.anchor", icon: Anchor },
  { value: "bell", labelKey: "agentBranding.icon.bell", icon: Bell },
  { value: "puzzle", labelKey: "agentBranding.icon.puzzle", icon: Puzzle },
  { value: "cloud", labelKey: "agentBranding.icon.cloud", icon: Cloud },
  { value: "moon", labelKey: "agentBranding.icon.moon", icon: Moon },
];

export const DEFAULT_AGENT_COLOR = "blue";
export const DEFAULT_AGENT_ICON = "bot";

const DEFAULT_PRIMARY_DESCRIPTIONS: Record<string, string> = {
  build: "默认的 Agent，执行通用的写作任务，并在需要时调度子 Agent 完成工作",
  plan: "专注于规划和协调，组织子 Agent 工作、审查与交付，负责执行系统写作的任务",
};

export function getAgentDisplayDescription(key: string, description: string): string {
  if (key === "build" || key === "plan") {
    if (description && description !== DEFAULT_PRIMARY_DESCRIPTIONS[key]) {
      return description;
    }
    return i18n.t(`agentBranding.primaryDescription.${key}`);
  }
  return description;
}

export function getAgentIcon(value?: string | null): LucideIcon {
  return AGENT_ICON_OPTIONS.find((option) => option.value === value)?.icon ?? GraduationCap;
}

export function getAgentColorVar(color?: string | null): string {
  const resolved = AGENT_COLOR_OPTIONS.some((option) => option.value === color)
    ? (color as string)
    : DEFAULT_AGENT_COLOR;
  return `var(--${resolved}-9)`;
}

export function getAgentIconColor(color?: string | null): string {
  const resolved = AGENT_COLOR_OPTIONS.some((option) => option.value === color)
    ? (color as string)
    : DEFAULT_AGENT_COLOR;
  return `color-mix(in oklab, var(--${resolved}-9) 80%, var(--gray-12))`;
}
