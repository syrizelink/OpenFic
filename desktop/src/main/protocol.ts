import { app, net, protocol, session } from "electron";
import { existsSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import type { RuntimeConfigResponse } from "../shared/config.js";
import { configureSystemProxy } from "./proxy.js";

let runtimeConfig: RuntimeConfigResponse | null = null;
const registeredPartitions = new Map<string, Promise<void>>();

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

    const filePath = url.hostname === "setup"
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
