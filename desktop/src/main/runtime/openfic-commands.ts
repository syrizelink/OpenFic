interface SpawnCommand {
  command: string;
  args: string[];
}

function getOpenFicCliPath(venvPythonPath: string): string {
  return process.platform === "win32"
    ? venvPythonPath.replace(/python\.exe$/i, "openfic.exe")
    : venvPythonPath.replace(/python$/i, "openfic");
}

export function createOpenFicProbeCommand(venvPythonPath: string): SpawnCommand {
  return {
    command: venvPythonPath,
    args: ["-m", "pip", "show", "openfic"],
  };
}

export function createOpenFicInstallCommand(venvPythonPath: string): Omit<SpawnCommand, "command"> {
  return {
    args: ["pip", "install", "--python", venvPythonPath, "openfic"],
  };
}

export function createOpenFicServeCommand(venvPythonPath: string, port: number): SpawnCommand {
  return {
    command: getOpenFicCliPath(venvPythonPath),
    args: ["serve", "--host", "127.0.0.1", "--port", String(port)],
  };
}
