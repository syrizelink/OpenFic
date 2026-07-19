import i18n from "@/i18n";

/**
 * Agent Definition Types
 *
 * 智能体定义前端类型，对齐后端 /agent-definitions API。
 */

export interface AgentDefinitionResponse {
  key: string;
  display_name: string;
  description: string;
  kind: "primary" | "subagent";
  prompt_agent_name: string;
  model_id: string | null;
  enabled_tool_categories: string[];
  enabled_skills: string[];
  metadata: Record<string, unknown>;
  enabled: boolean;
  source: "builtin" | "custom";
  delegatable_agents: string[];
}

export interface AgentDefinitionCreateRequest {
  key: string;
  display_name: string;
  description: string;
  kind: "primary" | "subagent";
  prompt_agent_name: string;
  model_id: string | null;
  enabled_tool_categories: string[];
  enabled_skills: string[];
  metadata: Record<string, unknown>;
  delegatable_agents: string[];
}

export interface AgentDefinitionUpdateRequest {
  display_name?: string | null;
  description?: string | null;
  kind?: "primary" | "subagent" | null;
  prompt_agent_name?: string | null;
  model_id?: string | null;
  enabled_tool_categories?: string[] | null;
  enabled_skills?: string[] | null;
  metadata?: Record<string, unknown> | null;
  enabled?: boolean | null;
  delegatable_agents?: string[] | null;
}

export interface AgentDefinitionListResponse {
  definitions: AgentDefinitionResponse[];
}

export interface AgentToolCategoryResponse {
  key: string;
  name: string;
  tool_keys: string[];
}

export interface AgentToolCategoryListResponse {
  categories: AgentToolCategoryResponse[];
}

export const SYSTEM_DEFAULT_MODEL_REFERENCE = "__system_default_model__";
export const SYSTEM_LIGHT_MODEL_REFERENCE = "__system_light_model__";

const AGENT_KIND_LABEL_KEYS: Record<string, string> = {
  primary: "settings.agentsKindPrimary",
  subagent: "settings.agentsKindSubagent",
};

export function getAgentKindOptions(): Array<{ value: "primary" | "subagent"; label: string }> {
  return [
    { value: "primary", label: i18n.t("settings.agentsKindPrimary") },
    { value: "subagent", label: i18n.t("settings.agentsKindSubagent") },
  ];
}

export function getAgentKindLabel(kind: string): string {
  return i18n.t(AGENT_KIND_LABEL_KEYS[kind] ?? kind, { defaultValue: kind });
}
