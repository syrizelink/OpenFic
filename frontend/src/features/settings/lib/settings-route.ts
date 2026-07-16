export const SETTINGS_ROUTE_CATEGORIES = [
  "general",
  "connections",
  "models",
  "index",
  "agent-tools",
  "rules",
  "skills",
  "agents",
  "advanced",
] as const;

export const MODEL_SETTINGS_TABS = ["llm", "embedding", "rerank"] as const;

export type SettingsRouteCategory = (typeof SETTINGS_ROUTE_CATEGORIES)[number];
export type ModelSettingsTab = (typeof MODEL_SETTINGS_TABS)[number];

export interface SettingsDialogRoute {
  category: SettingsRouteCategory;
  modelTab?: ModelSettingsTab;
}

export const DEFAULT_SETTINGS_ROUTE_CATEGORY: SettingsRouteCategory = "general";
export const DEFAULT_MODEL_SETTINGS_TAB: ModelSettingsTab = "llm";
