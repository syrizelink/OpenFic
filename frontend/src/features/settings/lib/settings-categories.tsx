import {
  Brain,
  Bot,
  Cable,
  Database,
  FileText,
  Globe,
  MessagesSquare,
  Palette,
  Package,
  Summary as SummaryIcon,
  Settings as SettingsIcon,
  ShieldAlert,
  SlidersHorizontal,
  Type,
} from "lucide-react";
import type { ReactNode } from "react";

export type SettingsCategory =
  | "general"
  | "personalization"
  | "editor"
  | "connections"
  | "models"
  | "index"
  | "context"
  | "summary"
  | "agent-tools"
  | "web-search"
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
    id: "personalization",
    icon: <Palette size={16} />,
    labelKey: "settings.personalization",
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
    id: "summary",
    icon: <SummaryIcon size={16} />,
    labelKey: "settings.summary",
  },
  {
    id: "agent-tools",
    icon: <ShieldAlert size={16} />,
    labelKey: "settings.agentTools",
  },
  {
    id: "web-search",
    icon: <Globe size={16} />,
    labelKey: "settings.webSearch",
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
