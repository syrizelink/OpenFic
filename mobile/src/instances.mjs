export const STORAGE_KEY = "openfic.mobile.instances.v1";

export function normalizeInstanceUrl(input) {
  const value = input.trim();
  if (!/^https?:\/\//i.test(value)) throw new Error("请输入完整的 http:// 或 https:// 地址。");
  const url = new URL(value);
  if (url.username || url.password) throw new Error("请勿在地址中填写用户名或密码。");
  if (url.pathname !== "/" || url.search || url.hash)
    throw new Error("请填写实例根地址，不包含页面路径或参数。");
  const host = url.hostname.toLowerCase();
  if (
    host === "localhost" ||
    host.endsWith(".localhost") ||
    host === "[::1]" ||
    host === "0.0.0.0" ||
    /^127\./.test(host)
  ) {
    throw new Error("请使用远程服务器或局域网地址，不能连接手机本机。");
  }
  return url.origin;
}

export function readInstances(storage) {
  try {
    const value = JSON.parse(storage.getItem(STORAGE_KEY) || "[]");
    if (!Array.isArray(value)) return [];
    return value.filter((item) => {
      if (
        !item ||
        typeof item.id !== "string" ||
        typeof item.name !== "string" ||
        typeof item.url !== "string"
      )
        return false;
      try {
        return normalizeInstanceUrl(item.url) === item.url;
      } catch {
        return false;
      }
    });
  } catch {
    return [];
  }
}
