import { Capacitor, registerPlugin } from "@capacitor/core";
interface RemoteInstancePlugin {
  check(options: { url: string }): Promise<{ version: string }>;
  open(options: { url: string; name: string }): Promise<void>;
}
const RemoteInstance = registerPlugin<RemoteInstancePlugin>("RemoteInstance");
export async function checkInstance(url: string): Promise<{ version: string }> {
  if (Capacitor.isNativePlatform()) return RemoteInstance.check({ url });
  const response = await fetch(`${url}/api/v1/health`, { signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error(`服务器返回 ${response.status}`);
  const data = await response.json();
  if (data.status !== "ok" && data.status !== "healthy")
    throw new Error("该地址不是可用的 OpenFic 实例。");
  return data;
}
export async function openInstance(url: string, name: string): Promise<void> {
  if (!Capacitor.isNativePlatform())
    throw new Error("请在 Android APP 中打开实例；浏览器预览仅用于检查连接界面。");
  await RemoteInstance.open({ url, name });
}
