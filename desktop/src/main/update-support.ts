export interface UpdateSupportEnvironment {
  platform: NodeJS.Platform;
  arch: string;
}

export function isAutoUpdateSupported(environment: UpdateSupportEnvironment): boolean {
  return environment.platform === "win32" && (environment.arch === "x64" || environment.arch === "arm64");
}
