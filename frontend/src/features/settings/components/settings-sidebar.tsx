import { Text } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";

import { SETTINGS_CATEGORY_ITEMS, type SettingsCategory } from "../lib/settings-categories";

/** 设置类目 */
interface SettingsSidebarProps {
  /** 当前选中的类目 */
  activeCategory: SettingsCategory;
  /** 类目变更回调 */
  onCategoryChange: (category: SettingsCategory) => void;
}

export function SettingsSidebar({ activeCategory, onCategoryChange }: SettingsSidebarProps) {
  const { t } = useTranslation();

  return (
    <nav
      className="settings-sidebar"
      aria-label={t("topbar.settings")}
    >
      <div className="settings-sidebar-list">
        {SETTINGS_CATEGORY_ITEMS.map((category) => {
          const isActive = activeCategory === category.id;
          return (
            <button
              key={category.id}
              type="button"
              onClick={() => onCategoryChange(category.id)}
              className={`settings-sidebar-item${isActive ? " settings-sidebar-item--active" : ""}`}
              aria-current={isActive ? "page" : undefined}
            >
              <span
                className="settings-sidebar-item-icon"
                aria-hidden="true"
              >
                {category.icon}
              </span>
              <Text
                size="2"
                weight={isActive ? "medium" : "regular"}
              >
                {t(category.labelKey)}
              </Text>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
