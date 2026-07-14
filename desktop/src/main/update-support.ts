export interface UpdateSupportEnvironment {
  platform: NodeJS.Platform;
  arch: string;
}

export function getUpdateArchitectureName(environment: UpdateSupportEnvironment): "x86_64" | "aarch64" | null {
  if (environment.platform !== "win32") return null;
  if (environment.arch === "x64") return "x86_64";
  if (environment.arch === "arm64") return "aarch64";
  return null;
}

export function isAutoUpdateSupported(environment: UpdateSupportEnvironment): boolean {
  return getUpdateArchitectureName(environment) !== null;
}
