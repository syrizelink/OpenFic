import type {
  ActiveSubagentState,
  AgentConversationDescriptor,
  AgentSessionStatus,
} from "@/lib/agent.types";

export interface AssistantSidebarState {
  agentStatus: AgentSessionStatus;
  isAgentRunning: boolean;
  conversationDescriptor?: AgentConversationDescriptor | null;
  activeSubagents?: ActiveSubagentState[];
}
