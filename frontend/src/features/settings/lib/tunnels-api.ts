import { apiClient } from "@/lib/api-client";

export type TunnelProvider = "cloudflare" | "ngrok";
export interface TunnelStatus {
  provider: TunnelProvider | null;
  mode: string | null;
  status: "stopped" | "starting" | "running" | "error";
  url: string | null;
  error: string | null;
  providers: Record<TunnelProvider, boolean>;
  auth_enabled: boolean;
  frontend_available: boolean;
}
export interface TunnelStartRequest {
  provider: TunnelProvider;
  mode: "quick" | "managed-remote";
  token?: string;
  hostname?: string;
}
export async function fetchTunnel(): Promise<TunnelStatus> {
  return (await apiClient.get("/tunnels")).data;
}
export async function startTunnel(request: TunnelStartRequest): Promise<void> {
  await apiClient.post("/tunnels/start", request);
}
export async function stopTunnel(): Promise<void> {
  await apiClient.post("/tunnels/stop");
}
