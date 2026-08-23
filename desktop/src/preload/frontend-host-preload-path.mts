import { fileURLToPath, pathToFileURL } from "node:url";

export function getFrontendHostPreloadPath(metaUrl: string): string {
  return pathToFileURL(fileURLToPath(new URL("./frontend-host-preload.cjs", metaUrl))).href;
}
