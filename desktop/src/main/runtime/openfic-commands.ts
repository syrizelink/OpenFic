interface SpawnCommand {
  command: string;
  args: string[];
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

export function createOpenFicServeCommand(uvPath: string, venvPythonPath: string, port: number): SpawnCommand {
  return {
    command: uvPath,
    args: ["run", "--python", venvPythonPath, "openfic", "serve", "--host", "127.0.0.1", "--port", String(port)],
  };
}
