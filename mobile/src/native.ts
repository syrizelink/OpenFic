import { Capacitor, registerPlugin } from "@capacitor/core";
interface RemoteInstancePlugin {
  scanUrl(): Promise<{ value: string | null }>;
  check(options: { url: string }): Promise<{ version: string }>;
  open(options: { url: string; name: string }): Promise<void>;
}
const RemoteInstance = registerPlugin<RemoteInstancePlugin>("RemoteInstance");
const platform = Capacitor.getPlatform(); // "android" | "ios" | "web"
// The RemoteInstance native plugin is currently Android-only.
const hasRemoteInstancePlugin = platform === "android";
export const supportsInstanceScanning = platform === "android";

export async function scanInstanceUrl(): Promise<string | null> {
  if (!supportsInstanceScanning) throw new Error("请在 Android APP 中扫描二维码。");
  const result = await RemoteInstance.scanUrl();
  return result.value;
}

export interface UpdateState {
  status: "unsupported" | "idle" | "available" | "checking" | "downloading" | "ready" | "error";
  currentVersion?: string;
  version?: string;
  progress?: number;
  message?: string;
}

interface AppUpdatePlugin {
  check(): Promise<UpdateState>;
  download(): Promise<UpdateState>;
  getStatus(): Promise<UpdateState>;
  install(): Promise<{ permissionRequired: boolean }>;
}

export const AppUpdate = registerPlugin<AppUpdatePlugin>("AppUpdate");
export const supportsAppUpdates = platform === "android";
export async function checkInstance(url: string): Promise<{ version: string }> {
  if (hasRemoteInstancePlugin) return RemoteInstance.check({ url });
  // iOS / web fallback: plain fetch (the ATS local-network exemption covers LAN http).
  const response = await fetch(`${url}/api/v1/health`, { signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error(`服务器返回 ${response.status}`);
  const data = await response.json();
  if (data.status !== "ok" && data.status !== "healthy")
    throw new Error("该地址不是可用的 OpenFic 实例。");
  if (typeof data.version !== "string" || !data.version)
    throw new Error("该地址不是可用的 OpenFic 实例。");
  return { version: data.version };
}
export async function openInstance(url: string, name: string): Promise<void> {
  if (hasRemoteInstancePlugin) return RemoteInstance.open({ url, name });
  if (platform === "ios") {
    // TODO: add a native iOS plugin (dedicated view controller) in a follow-up.
    window.location.href = url;
    return;
  }
  throw new Error("请在 Android APP 中打开实例；浏览器预览仅用于检查连接界面。");
}
