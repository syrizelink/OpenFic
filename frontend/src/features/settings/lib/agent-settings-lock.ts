import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect } from "react";

import { apiClient } from "@/lib/api-client";
import { getSocket } from "@/lib/socket-client";

export const AGENT_SETTINGS_LOCK_QUERY_KEY = ["agent-settings-lock"] as const;

interface AgentSettingsLockResponse {
  is_locked: boolean;
}

interface AgentSettingsLockErrorDetail {
  code?: string;
}

export async function fetchAgentSettingsLock(): Promise<boolean> {
  const response = await apiClient.get<AgentSettingsLockResponse>("/settings/agent-session-lock");
  return response.data.is_locked === true;
}

export function useAgentSettingsLock() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: AGENT_SETTINGS_LOCK_QUERY_KEY,
    queryFn: fetchAgentSettingsLock,
    staleTime: 0,
    refetchOnMount: "always",
  });

  useEffect(() => {
    const socket = getSocket();
    const handleLockStateChanged = () => {
      void queryClient.invalidateQueries({ queryKey: AGENT_SETTINGS_LOCK_QUERY_KEY });
    };

    socket.on("agent:settings_lock_changed", handleLockStateChanged);
    return () => {
      socket.off("agent:settings_lock_changed", handleLockStateChanged);
    };
  }, [queryClient]);

  return query;
}

export function isAgentSettingsLockedError(error: unknown): boolean {
  if (!axios.isAxiosError(error) || error.response?.status !== 409) return false;
  const detail = error.response.data?.detail as AgentSettingsLockErrorDetail | undefined;
  return detail?.code === "agent_settings_locked";
}
