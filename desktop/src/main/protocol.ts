import { app, net, protocol, session } from "electron";
import { existsSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import type { RuntimeConfigResponse } from "../shared/config.js";
import { configureSystemProxy } from "./proxy.js";

let runtimeConfig: RuntimeConfigResponse | null = null;
const registeredPartitions = new Map<string, Promise<void>>();
const SHARED_FONT_CSS_PATH = "/frontend-fonts.css";
const SHARED_FONT_PREFIX = "/frontend-fonts/";

export function setRuntimeConfig(config: RuntimeConfigResponse): void {
  runtimeConfig = config;
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
  if (relativeToRoot.startsWith("..") || path.isAbsolute(relativeToRoot)) return path.join(resolvedRoot, "index.html");
  if (existsSync(candidate)) return candidate;
  return path.join(resolvedRoot, "index.html");
}

function resolveSetupStaticPath(rootDir: string, pathname: string): string {
  const normalizedPath = decodeURIComponent(pathname).replace(/^\/+/, "").replace(/^setup\//, "");
  const resolvedRoot = path.resolve(rootDir);
  const candidate = path.resolve(resolvedRoot, normalizedPath || "ui.html");
  const relativeToRoot = path.relative(resolvedRoot, candidate);
  if (relativeToRoot.startsWith("..") || path.isAbsolute(relativeToRoot)) return path.join(resolvedRoot, "ui.html");
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

  if (url.hostname === "setup" && (url.pathname === SHARED_FONT_CSS_PATH || url.pathname.startsWith(SHARED_FONT_PREFIX))) {
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
  const registration = configureSystemProxy(targetSession).then(() => {
    targetSession.protocol.handle("app", handleAppRequest);
  });
  registeredPartitions.set(partition, registration);
  return registration;
}
