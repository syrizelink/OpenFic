import { readdir, rename, rm } from "node:fs/promises";
import path from "node:path";

const outputDirectory = path.resolve(process.argv[2] ?? "dist-electron");
const architectureNames = new Map([
  ["arm_aarch64", "aarch64"],
  ["x64", "x86_64"],
  ["arm64", "aarch64"],
]);

function normalizeArtifactName(fileName) {
  let normalized = fileName;
  for (const [electronArch, artifactArch] of architectureNames) {
    normalized = normalized.replaceAll(`-${electronArch}-`, `-${artifactArch}-`);
    normalized = normalized.replaceAll(`-${electronArch}.`, `-${artifactArch}.`);
  }
  return normalized;
}

for (const entry of await readdir(outputDirectory, { withFileTypes: true })) {
  if (!entry.isFile()) continue;
  const normalizedName = normalizeArtifactName(entry.name);
  if (normalizedName === entry.name) continue;
  await rename(path.join(outputDirectory, entry.name), path.join(outputDirectory, normalizedName));
}

for (const entry of await readdir(outputDirectory, { withFileTypes: true })) {
  if (!entry.isFile()) continue;
  if (!/^OpenFic-.+-win-setup\.exe(?:\.blockmap)?$/.test(entry.name)) continue;
  if (entry.name.includes("-win-x86_64-setup") || entry.name.includes("-win-aarch64-setup")) continue;
  await rm(path.join(outputDirectory, entry.name));
}
