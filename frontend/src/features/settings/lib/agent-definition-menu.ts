import type { AgentDefinitionResponse } from "./agent-definitions.types";

export const AGENT_DEFINITION_MENU_ACTIONS = {
  copy: "copy",
  delete: "delete",
  reset: "reset",
} as const;

export type AgentDefinitionMenuAction =
  (typeof AGENT_DEFINITION_MENU_ACTIONS)[keyof typeof AGENT_DEFINITION_MENU_ACTIONS];

export function getAgentDefinitionMenuActions(
  definition: Pick<AgentDefinitionResponse, "source">
): AgentDefinitionMenuAction[] {
  if (definition.source === "builtin") {
    return [
      AGENT_DEFINITION_MENU_ACTIONS.copy,
      AGENT_DEFINITION_MENU_ACTIONS.reset,
    ];
  }

  return [
    AGENT_DEFINITION_MENU_ACTIONS.copy,
    AGENT_DEFINITION_MENU_ACTIONS.delete,
  ];
}
