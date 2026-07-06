import {
  Brain,
  Bot,
  Cable,
  Database,
  FileText,
  Package,
  Settings as SettingsIcon,
  ShieldAlert,
} from "lucide-react";
import type { ReactNode } from "react";

export type SettingsCategory =
  | "general"
  | "connections"
  | "models"
  | "index"
  | "agent-tools"
  | "rules"
  | "skills"
  | "agents";

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
];
