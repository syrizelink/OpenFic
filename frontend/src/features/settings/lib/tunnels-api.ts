import { apiClient } from "@/lib/api-client";

export type TunnelProvider = "cloudflare" | "ngrok";
export type TunnelMode = "quick" | "managed-remote";
export interface TunnelConfig {
  provider: TunnelProvider;
  mode: TunnelMode;
  hostname: string | null;
  token_configured: boolean;
}
export interface TunnelStatus {
  provider: TunnelProvider | null;
  mode: string | null;
  status: "stopped" | "starting" | "running" | "error";
  url: string | null;
  error: string | null;
  error_message: string | null;
  providers: Record<TunnelProvider, boolean>;
  auth_enabled: boolean;
  frontend_available: boolean;
  config: TunnelConfig;
}
export interface TunnelStatusEvent {
  provider: TunnelProvider | null;
  mode: string | null;
  status: TunnelStatus["status"];
  url: string | null;
  error: string | null;
  error_message: string | null;
  providers: Record<TunnelProvider, boolean>;
}
export interface TunnelStartRequest {
  provider: TunnelProvider;
  mode: TunnelMode;
  token?: string;
  hostname?: string;
}
export interface TunnelConfigUpdate {
  provider: TunnelProvider;
  mode: TunnelMode;
  hostname: string | null;
  token?: string;
}
export async function fetchTunnel(): Promise<TunnelStatus> {
  return (await apiClient.get("/tunnels")).data;
}
export async function startTunnel(request: TunnelStartRequest): Promise<void> {
  await apiClient.post("/tunnels/start", request);
}
export async function updateTunnelConfig(request: TunnelConfigUpdate): Promise<TunnelConfig> {
  return (await apiClient.put("/tunnels/config", request)).data;
}
export async function stopTunnel(): Promise<void> {
  await apiClient.post("/tunnels/stop");
}
