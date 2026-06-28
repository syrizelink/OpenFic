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
  tool_category_keys: string[];
  enabled_skill_ids: string[];
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
  tool_category_keys: string[];
  enabled_skill_ids: string[];
  metadata: Record<string, unknown>;
  delegatable_agents: string[];
}

export interface AgentDefinitionUpdateRequest {
  display_name?: string | null;
  description?: string | null;
  kind?: "primary" | "subagent" | null;
  prompt_agent_name?: string | null;
  model_id?: string | null;
  tool_category_keys?: string[] | null;
  enabled_skill_ids?: string[] | null;
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

export const AGENT_KIND_LABELS: Record<string, string> = {
  primary: "主",
  subagent: "子",
};

export const AGENT_KIND_OPTIONS = [
  { value: "primary", label: "主智能体 (Primary)" },
  { value: "subagent", label: "子智能体 (Subagent)" },
] as const;
