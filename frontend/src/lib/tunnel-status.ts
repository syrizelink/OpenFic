import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { subscribeTunnelStatus } from "@/features/settings/lib/tunnel-socket";
import { fetchTunnel, type TunnelStatus } from "@/features/settings/lib/tunnels-api";

export const TUNNEL_STATUS_QUERY_KEY = ["tunnels"] as const;

export function useTunnelStatus() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: TUNNEL_STATUS_QUERY_KEY,
    queryFn: fetchTunnel,
    refetchOnMount: "always",
  });

  useEffect(() => {
    return subscribeTunnelStatus(
      (status) => {
        queryClient.setQueryData<TunnelStatus>(TUNNEL_STATUS_QUERY_KEY, (current) =>
          current ? { ...current, ...status } : current,
        );
      },
      () => {
        void queryClient.invalidateQueries({ queryKey: TUNNEL_STATUS_QUERY_KEY });
      },
    );
  }, [queryClient]);

  return query;
}
