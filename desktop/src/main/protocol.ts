import { app, net, protocol } from "electron";
import { existsSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import type { RuntimeConfigResponse } from "../shared/config.js";

let runtimeConfig: RuntimeConfigResponse | null = null;

export function setRuntimeConfig(config: RuntimeConfigResponse): void {
  runtimeConfig = config;
}

export function getFrontendDistDir(): string {
  if (app.isPackaged) return path.join(process.resourcesPath, "frontend-dist");
  return path.join(app.getAppPath(), "..", "frontend", "dist");
}

export function getSetupDistDir(): string {
  return path.join(app.getAppPath(), "dist", "setup-ui");
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

export function handleAppProtocol(): void {
  protocol.handle("app", async (request) => {
    const url = new URL(request.url);

    if (url.pathname === "/runtime-config.json") {
      return new Response(JSON.stringify(runtimeConfig), {
        headers: { "content-type": "application/json; charset=utf-8" },
      });
    }

    const rootDir = url.hostname === "setup" ? getSetupDistDir() : getFrontendDistDir();
    const filePath = resolveStaticPath(rootDir, url.pathname);
    return net.fetch(pathToFileURL(filePath).toString());
  });
}
