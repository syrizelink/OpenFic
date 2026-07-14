export interface UpdateSupportEnvironment {
  platform: NodeJS.Platform;
  arch: string;
  hasNsisUninstaller?: boolean;
}

export function isAutoUpdateSupported(environment: UpdateSupportEnvironment): boolean {
  if (environment.platform === "win32") {
    return environment.arch === "x64" && environment.hasNsisUninstaller === true;
  }

  return false;
}
