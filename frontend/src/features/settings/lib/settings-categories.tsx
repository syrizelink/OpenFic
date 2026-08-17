import {
  Brain,
  Bot,
  Cable,
  Database,
  FileText,
  MessagesSquare,
  Package,
  Settings as SettingsIcon,
  ShieldAlert,
  SlidersHorizontal,
  Type,
} from "lucide-react";
import type { ReactNode } from "react";

export type SettingsCategory =
  | "general"
  | "editor"
  | "connections"
  | "models"
  | "index"
  | "context"
  | "agent-tools"
  | "rules"
  | "skills"
  | "agents"
  | "advanced";

interface SettingsCategoryItem {
  id: SettingsCategory;
  icon: ReactNode;
  labelKey: string;
}

export const SETTINGS_CATEGORY_ITEMS: SettingsCategoryItem[] = [
  {
    id: "general",
    icon: <SettingsIcon size={16} />,
    labelKey: "settings.general",
  },
  {
    id: "editor",
    icon: <Type size={16} />,
    labelKey: "settings.editor",
  },
  {
    id: "connections",
    icon: <Cable size={16} />,
    labelKey: "settings.connections",
  },
  {
    id: "models",
    icon: <Brain size={16} />,
    labelKey: "settings.models",
  },
  {
    id: "index",
    icon: <Database size={16} />,
    labelKey: "settings.index",
  },
  {
    id: "context",
    icon: <MessagesSquare size={16} />,
    labelKey: "settings.context",
  },
  {
    id: "agent-tools",
    icon: <ShieldAlert size={16} />,
    labelKey: "settings.agentTools",
  },
  {
    id: "rules",
    icon: <FileText size={16} />,
    labelKey: "settings.rules",
  },
  {
    id: "skills",
    icon: <Package size={16} />,
    labelKey: "settings.skills",
  },
  {
    id: "agents",
    icon: <Bot size={16} />,
    labelKey: "settings.agents",
  },
  {
    id: "advanced",
    icon: <SlidersHorizontal size={16} />,
    labelKey: "settings.advanced",
  },
];
