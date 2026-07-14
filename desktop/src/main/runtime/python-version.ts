export function matchesPortablePythonVersion(output: string, expectedVersion: string): boolean {
  const match = output.match(/\bPython\s+(\d+\.\d+\.\d+)\b/);
  return match?.[1] === expectedVersion;
}
