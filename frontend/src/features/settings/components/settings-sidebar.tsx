import { Text } from "@radix-ui/themes";
import { Settings as SettingsIcon, Cable, Brain, Database, ShieldAlert, Bot, Package, FileText } from "lucide-react";
import { useTranslation } from "react-i18next";

/** 设置类目 */
export type SettingsCategory =
  | "general"
  | "connections"
  | "models"
  | "index"
  | "agent-tools"
  | "rules"
  | "skills"
  | "agents";

interface SettingsSidebarProps {
  /** 当前选中的类目 */
  activeCategory: SettingsCategory;
  /** 类目变更回调 */
  onCategoryChange: (category: SettingsCategory) => void;
}

/** 类目配置 */
interface CategoryItem {
  id: SettingsCategory;
  icon: React.ReactNode;
  labelKey: string;
}

const CATEGORIES: CategoryItem[] = [
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

export function SettingsSidebar({
  activeCategory,
  onCategoryChange,
}: SettingsSidebarProps) {
  const { t } = useTranslation();

  return (
    <nav className="settings-sidebar" aria-label={t("topbar.settings")}>
      <div className="settings-sidebar-list">
        {CATEGORIES.map((category) => {
          const isActive = activeCategory === category.id;
          return (
            <button
              key={category.id}
              type="button"
              onClick={() => onCategoryChange(category.id)}
              className={`settings-sidebar-item${isActive ? " settings-sidebar-item--active" : ""}`}
              aria-current={isActive ? "page" : undefined}
            >
              <span className="settings-sidebar-item-icon" aria-hidden="true">
                {category.icon}
              </span>
              <Text size="2" weight={isActive ? "medium" : "regular"}>
                {t(category.labelKey)}
              </Text>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
