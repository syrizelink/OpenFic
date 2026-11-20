import { Badge, Flex, Text } from "@radix-ui/themes";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { PluginIcon } from "@/features/plugins/plugin-icon";

import { SETTINGS_CATEGORY_ITEMS, type SettingsCategory } from "../lib/settings-categories";

export interface SettingsPluginItem {
  id: string;
  title: string;
  icon: string;
  iconUrl?: string;
}

export function SettingsPluginIcon({ item }: { item: SettingsPluginItem }) {
  const [failed, setFailed] = useState(false);
  if (item.iconUrl && !failed)
    return (
      <img
        src={item.iconUrl}
        alt=""
        width={16}
        height={16}
        onError={() => setFailed(true)}
      />
    );
  return (
    <PluginIcon
      name={item.iconUrl ? "Puzzle" : item.icon}
      size={16}
    />
  );
}

/** 设置类目 */
interface SettingsSidebarProps {
  /** 当前选中的类目 */
  activeCategory: SettingsCategory;
  /** 类目变更回调 */
  onCategoryChange: (category: SettingsCategory) => void;
  pluginItems: SettingsPluginItem[];
  activePluginId: string | null;
  onPluginChange: (id: string) => void;
}

export function SettingsSidebar({
  activeCategory,
  onCategoryChange,
  pluginItems,
  activePluginId,
  onPluginChange,
}: SettingsSidebarProps) {
  const { t } = useTranslation();

  return (
    <nav
      className="settings-sidebar"
      aria-label={t("topbar.settings")}
    >
      <div className="settings-sidebar-list">
        {SETTINGS_CATEGORY_ITEMS.map((category) => {
          const isActive = activePluginId === null && activeCategory === category.id;
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
              <Flex
                align="center"
                gap="2"
                className="settings-sidebar-item-label"
              >
                <Text
                  size="2"
                  weight={isActive ? "medium" : "regular"}
                >
                  {t(category.labelKey)}
                </Text>
                {category.badgeKey ? (
                  <Badge
                    size="1"
                    variant="soft"
                    color="green"
                  >
                    {t(category.badgeKey)}
                  </Badge>
                ) : null}
              </Flex>
            </button>
          );
        })}
        {pluginItems.map((item) => {
          const isActive = activePluginId === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onPluginChange(item.id)}
              className={`settings-sidebar-item${isActive ? " settings-sidebar-item--active" : ""}`}
              aria-current={isActive ? "page" : undefined}
            >
              <span
                className="settings-sidebar-item-icon"
                aria-hidden="true"
              >
                <SettingsPluginIcon
                  key={item.iconUrl ?? item.icon}
                  item={item}
                />
              </span>
              <Flex
                align="center"
                gap="2"
                className="settings-sidebar-item-label"
              >
                <Text
                  size="2"
                  weight={isActive ? "medium" : "regular"}
                >
                  {item.title}
                </Text>
              </Flex>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
