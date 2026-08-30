import type {
  ActiveSubagentState,
  AgentSessionChanges,
  AgentSessionStateResponse,
} from "@/lib/agent.types";
import type { Task } from "@/lib/task.types";

export interface AgentTaskBundleLoaders {
  fetchTask: (taskId: string) => Promise<Task>;
  fetchAgentSessionState: (sessionId: string) => Promise<AgentSessionStateResponse>;
  fetchActiveSubagents: (parentSessionId: string) => Promise<ActiveSubagentState[]>;
  fetchAgentSessionChanges: (sessionId: string) => Promise<AgentSessionChanges>;
}

export interface AgentTaskBundle {
  task: Task;
  sessionState: AgentSessionStateResponse | null;
  activeSubagentRows: ActiveSubagentState[];
  sessionChanges: AgentSessionChanges | null;
}

export async function loadAgentTaskBundle(
  taskId: string,
  loaders: AgentTaskBundleLoaders,
): Promise<AgentTaskBundle> {
  const task = await loaders.fetchTask(taskId);
  if (!task.agentSessionId) {
    return {
      task,
      sessionState: null,
      activeSubagentRows: [],
      sessionChanges: null,
    };
  }

  const [sessionStateResult, activeSubagentsResult, sessionChangesResult] =
    await Promise.allSettled([
      loaders.fetchAgentSessionState(task.agentSessionId),
      loaders.fetchActiveSubagents(task.agentSessionId),
      loaders.fetchAgentSessionChanges(task.agentSessionId),
    ]);

  return {
    task,
    sessionState: sessionStateResult.status === "fulfilled" ? sessionStateResult.value : null,
    activeSubagentRows:
      activeSubagentsResult.status === "fulfilled"
        ? activeSubagentsResult.value.filter((item) => item.isActive)
        : [],
    sessionChanges: sessionChangesResult.status === "fulfilled" ? sessionChangesResult.value : null,
  };
}
