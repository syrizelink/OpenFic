import { existsSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { app, net, protocol, session } from "electron";

import type { RuntimeConfigResponse } from "../shared/config.js";
import { appendLog } from "./logging.js";
import { configureSystemProxy } from "./proxy.js";
import { isNgrokUrl } from "./remote-url.js";

let runtimeConfig: RuntimeConfigResponse | null = null;
const registeredPartitions = new Map<string, Promise<void>>();
const configuredAuthSessions = new WeakSet<Electron.Session>();
const capturedAuthCookies = new WeakMap<Electron.Session, { origin: string; value: string; expiresAt?: number }>();
const SHARED_FONT_CSS_PATH = "/frontend-fonts.css";
const SHARED_FONT_PREFIX = "/frontend-fonts/";
const AUTH_COOKIE_NAME = "openfic_auth";

export function setRuntimeConfig(config: RuntimeConfigResponse): void {
  runtimeConfig = config;
}

function getHeaderValues(headers: Record<string, string[]>, name: string): string[] {
  const headerName = Object.keys(headers).find((key) => key.toLowerCase() === name);
  return headerName ? (headers[headerName] ?? []) : [];
}

function getAuthCookieFromSetCookie(headers: Record<string, string[]>): string | null {
  for (const header of getHeaderValues(headers, "set-cookie")) {
    const match = header.match(new RegExp(`^(${AUTH_COOKIE_NAME}=[^;]*)`, "i"));
    if (match) return header;
  }
  return null;
}

async function saveAuthCookie(targetSession: Electron.Session, url: string, header: string): Promise<void> {
  const parts = header.split(";").map((part) => part.trim());
  const value = parts[0].slice(parts[0].indexOf("=") + 1);
  const maxAgePart = parts.slice(1).find((part) => /^max-age=/i.test(part));
  const maxAgeText = maxAgePart?.slice(maxAgePart.indexOf("=") + 1);
  const maxAge = maxAgeText && /^-?\d+$/.test(maxAgeText) ? Number(maxAgeText) : undefined;
  const expiresAt = maxAge !== undefined && Number.isFinite(maxAge) ? Date.now() / 1000 + maxAge : undefined;
  const origin = new URL(url).origin;

  if (!value || (expiresAt !== undefined && expiresAt <= Date.now() / 1000)) {
    capturedAuthCookies.delete(targetSession);
    await targetSession.cookies.remove(origin, AUTH_COOKIE_NAME);
  } else {
    capturedAuthCookies.set(targetSession, { origin, value, expiresAt });
    await targetSession.cookies.set({
      url: origin,
      name: AUTH_COOKIE_NAME,
      value,
      path: "/",
      httpOnly: true,
      secure: parts.some((part) => /^secure$/i.test(part)),
      sameSite: "lax",
      ...(expiresAt !== undefined ? { expirationDate: expiresAt } : {}),
    });
  }
  await targetSession.cookies.flushStore();
}

function getCapturedAuthCookie(targetSession: Electron.Session, url: string): string | undefined {
  const cookie = capturedAuthCookies.get(targetSession);
  if (!cookie || cookie.origin !== new URL(url).origin) return undefined;
  if (cookie.expiresAt !== undefined && cookie.expiresAt <= Date.now() / 1000) {
    capturedAuthCookies.delete(targetSession);
    return undefined;
  }
  return `${AUTH_COOKIE_NAME}=${cookie.value}`;
}

function isBackendRequest(url: string): boolean {
  if (!runtimeConfig?.backendBaseUrl) return false;
  try {
    return new URL(url).origin === new URL(runtimeConfig.backendBaseUrl).origin;
  } catch {
    return false;
  }
}

function addAuthCookie(requestHeaders: Record<string, string>, authCookie: string): void {
  const cookieHeaderName =
    Object.keys(requestHeaders).find((key) => key.toLowerCase() === "cookie") ?? "Cookie";
  const existingCookies = (requestHeaders[cookieHeaderName] ?? "")
    .split(";")
    .map((cookie) => cookie.trim())
    .filter((cookie) => cookie && !cookie.toLowerCase().startsWith(`${AUTH_COOKIE_NAME}=`));
  requestHeaders[cookieHeaderName] = [...existingCookies, authCookie].join("; ");
}

function configureAuthSession(targetSession: Electron.Session): void {
  if (configuredAuthSessions.has(targetSession)) return;
  configuredAuthSessions.add(targetSession);

  targetSession.webRequest.onHeadersReceived((details, callback) => {
    if (isBackendRequest(details.url)) {
      const authCookie = getAuthCookieFromSetCookie(details.responseHeaders ?? {});
      if (authCookie) {
        // The app:// frontend is cross-site, so Chromium may reject the backend's
        // SameSite=Lax cookie. Store it in this instance's session explicitly.
        void saveAuthCookie(targetSession, details.url, authCookie)
          .catch((error: unknown) => {
            appendLog("auth", `保存认证 Cookie 失败：${error instanceof Error ? error.message : String(error)}`);
          })
          .finally(() => callback({ responseHeaders: details.responseHeaders }));
        return;
      }
    }
    callback({ responseHeaders: details.responseHeaders });
  });

  targetSession.webRequest.onBeforeSendHeaders((details, callback) => {
    if (!isBackendRequest(details.url)) {
      callback({ requestHeaders: details.requestHeaders });
      return;
    }

    if (isNgrokUrl(runtimeConfig?.backendBaseUrl ?? "")) {
      details.requestHeaders["ngrok-skip-browser-warning"] = "1";
    }

    void targetSession.cookies
      .get({ url: runtimeConfig?.backendBaseUrl ?? details.url, name: AUTH_COOKIE_NAME })
      .then((cookies) => {
        const authCookie = cookies[0]
          ? `${AUTH_COOKIE_NAME}=${cookies[0].value}`
          : getCapturedAuthCookie(targetSession, details.url);
        if (authCookie) addAuthCookie(details.requestHeaders, authCookie);
        callback({ requestHeaders: details.requestHeaders });
      })
      .catch(() => {
        const authCookie = getCapturedAuthCookie(targetSession, details.url);
        if (authCookie) addAuthCookie(details.requestHeaders, authCookie);
        callback({ requestHeaders: details.requestHeaders });
      });
  });
}

export function getFrontendDistDir(): string {
  if (app.isPackaged) return path.join(process.resourcesPath, "frontend-dist");
  return path.join(app.getAppPath(), "..", "frontend", "dist");
}

export function getSetupDistDir(): string {
  return path.join(app.getAppPath(), "dist", "ui");
}

function resolveStaticPath(rootDir: string, pathname: string): string {
  const resolvedRoot = path.resolve(rootDir);
  const relativePath = decodeURIComponent(pathname).replace(/^\/+/, "");
  const candidate = path.resolve(resolvedRoot, relativePath || "index.html");
  const relativeToRoot = path.relative(resolvedRoot, candidate);
  if (relativeToRoot.startsWith("..") || path.isAbsolute(relativeToRoot))
    return path.join(resolvedRoot, "index.html");
  if (existsSync(candidate)) return candidate;
  return path.join(resolvedRoot, "index.html");
}

function resolveSetupStaticPath(rootDir: string, pathname: string): string {
  const normalizedPath = decodeURIComponent(pathname)
    .replace(/^\/+/, "")
    .replace(/^setup\//, "");
  const resolvedRoot = path.resolve(rootDir);
  const candidate = path.resolve(resolvedRoot, normalizedPath || "ui.html");
  const relativeToRoot = path.relative(resolvedRoot, candidate);
  if (relativeToRoot.startsWith("..") || path.isAbsolute(relativeToRoot))
    return path.join(resolvedRoot, "ui.html");
  if (existsSync(candidate)) return candidate;
  return path.join(resolvedRoot, "ui.html");
}

function resolveContainedPath(rootDir: string, relativePath: string): string | null {
  const resolvedRoot = path.resolve(rootDir);
  const candidate = path.resolve(resolvedRoot, relativePath);
  const relativeToRoot = path.relative(resolvedRoot, candidate);
  if (relativeToRoot.startsWith("..") || path.isAbsolute(relativeToRoot)) return null;
  return existsSync(candidate) ? candidate : null;
}

function resolveSharedFontPath(pathname: string): string | null {
  if (pathname === SHARED_FONT_CSS_PATH) {
    return resolveContainedPath(getFrontendDistDir(), "font-faces.css");
  }

  if (!pathname.startsWith(SHARED_FONT_PREFIX)) return null;
  const relativePath = decodeURIComponent(pathname.slice(SHARED_FONT_PREFIX.length));
  return resolveContainedPath(path.join(getFrontendDistDir(), "fonts"), relativePath);
}

export function registerAppScheme(): void {
  protocol.registerSchemesAsPrivileged([
    {
      scheme: "app",
      privileges: {
        standard: true,
        secure: true,
        supportFetchAPI: true,
        corsEnabled: true,
      },
    },
  ]);
}

async function handleAppRequest(request: Request): Promise<Response> {
  const url = new URL(request.url);

  if (url.pathname === "/runtime-config.json") {
    return new Response(JSON.stringify(runtimeConfig), {
      headers: { "content-type": "application/json; charset=utf-8" },
    });
  }

  if (
    url.hostname === "setup" &&
    (url.pathname === SHARED_FONT_CSS_PATH || url.pathname.startsWith(SHARED_FONT_PREFIX))
  ) {
    const sharedFontPath = resolveSharedFontPath(url.pathname);
    if (!sharedFontPath) return new Response("Not Found", { status: 404 });
    return net.fetch(pathToFileURL(sharedFontPath).toString());
  }

  const filePath =
    url.hostname === "setup"
      ? resolveSetupStaticPath(getSetupDistDir(), url.pathname)
      : resolveStaticPath(getFrontendDistDir(), url.pathname);
  return net.fetch(pathToFileURL(filePath).toString());
}

export function handleAppProtocol(): void {
  protocol.handle("app", handleAppRequest);
}

export function ensureAppProtocolForPartition(partition: string): Promise<void> {
  if (!partition) return Promise.resolve();
  const registered = registeredPartitions.get(partition);
  if (registered) return registered;

  const targetSession = session.fromPartition(partition);
  configureAuthSession(targetSession);
  const registration = configureSystemProxy(targetSession).then(() => {
    targetSession.protocol.handle("app", handleAppRequest);
  });
  registeredPartitions.set(partition, registration);
  return registration;
}
