import { session, type Session } from "electron";

const configuredSessions = new WeakMap<Session, Promise<void>>();
const LOCAL_BYPASS_HOSTS = ["localhost", "127.0.0.1"];
const INVALID_NO_PROXY_HOSTS = new Set(["::1", "[::1]"]);

export function configureSystemProxy(targetSession: Session): Promise<void> {
  const configured = configuredSessions.get(targetSession);
  if (configured) return configured;

  const configuration = targetSession.setProxy({ mode: "system" }).catch((error: unknown) => {
    console.warn("Unable to configure the system proxy:", error);
  });
  configuredSessions.set(targetSession, configuration);
  return configuration;
}

export function configureDefaultSystemProxy(): Promise<void> {
  return configureSystemProxy(session.defaultSession);
}

function getProxyUrl(proxyRules: string): string | null {
  for (const rule of proxyRules.split(";")) {
    const match = rule.trim().match(/^(PROXY|HTTPS|SOCKS|SOCKS4|SOCKS5)\s+(.+)$/i);
    if (!match) continue;

    const [, scheme, address] = match;
    const normalizedScheme = scheme.toUpperCase();
    const protocol = normalizedScheme === "HTTPS" ? "https" : normalizedScheme.startsWith("SOCKS") ? normalizedScheme.toLowerCase() : "http";
    return `${protocol}://${address.trim()}`;
  }
  return null;
}

function withLocalBypass(currentValue: string | undefined): string {
  const hosts =
    currentValue
      ?.split(",")
      .map((host) => host.trim())
      .filter((host) => host && !INVALID_NO_PROXY_HOSTS.has(host)) ?? [];
  for (const host of LOCAL_BYPASS_HOSTS) {
    if (!hosts.includes(host)) hosts.push(host);
  }
  return hosts.join(",");
}

/**
 * Child processes do not use Chromium's proxy service. Resolve the active system
 * proxy and expose it through the conventional variables they understand.
 */
export async function getSystemProxyEnvironment(url: string): Promise<NodeJS.ProcessEnv> {
  await configureDefaultSystemProxy();
  const proxyUrl = getProxyUrl(await session.defaultSession.resolveProxy(url));
  const noProxy = withLocalBypass(process.env.NO_PROXY ?? process.env.no_proxy);
  if (!proxyUrl) return { NO_PROXY: noProxy, no_proxy: noProxy };

  return {
    HTTP_PROXY: proxyUrl,
    HTTPS_PROXY: proxyUrl,
    ALL_PROXY: proxyUrl,
    http_proxy: proxyUrl,
    https_proxy: proxyUrl,
    all_proxy: proxyUrl,
    NO_PROXY: noProxy,
    no_proxy: noProxy,
  };
}
