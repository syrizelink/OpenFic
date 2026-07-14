import { createHash } from "node:crypto";
import { access, readFile, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";

const outputDirectory = path.resolve(process.argv[2] ?? "dist-electron");
const packageJson = JSON.parse(await readFile(path.resolve("package.json"), "utf8"));
const version = process.env.OPENFIC_UPDATE_VERSION ?? packageJson.version;
const architectures = ["x86_64", "aarch64"];

async function exists(filePath) {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function getFileInfo(fileName) {
  const filePath = path.join(outputDirectory, fileName);
  const contents = await readFile(filePath);
  const fileStats = await stat(filePath);
  return {
    fileName,
    sha512: createHash("sha512").update(contents).digest("base64"),
    size: fileStats.size,
  };
}

const universalInstaller = `OpenFic-${version}-win-setup.exe`;
for (const fileName of [universalInstaller, `${universalInstaller}.blockmap`]) {
  const filePath = path.join(outputDirectory, fileName);
  if (await exists(filePath)) await rm(filePath);
}

const files = await Promise.all(
  architectures.map(async (architecture) => ({
    architecture,
    ...(await getFileInfo(`OpenFic-${version}-win-${architecture}-setup.exe`)),
  })),
);
const releaseDate = new Date().toISOString();

function createUpdateInfo(file, compatibilityArchitecture) {
  const url = compatibilityArchitecture ? `${file.fileName}?arch=${compatibilityArchitecture}` : file.fileName;
  return [
    `version: ${version}`,
    "files:",
    `  - url: ${url}`,
    `    sha512: ${file.sha512}`,
    `    size: ${file.size}`,
    `path: ${url}`,
    `sha512: ${file.sha512}`,
    `releaseDate: '${releaseDate}'`,
    "",
  ].join("\n");
}

const legacyArchitectures = ["x64", "arm64"];
const legacyLatestYml = [
  `version: ${version}`,
  "files:",
  ...files.flatMap((file, index) => [
    `  - url: ${file.fileName}?arch=${legacyArchitectures[index]}`,
    `    sha512: ${file.sha512}`,
    `    size: ${file.size}`,
  ]),
  `path: ${files[0].fileName}?arch=${legacyArchitectures[0]}`,
  `sha512: ${files[0].sha512}`,
  `releaseDate: '${releaseDate}'`,
  "",
].join("\n");

await Promise.all([
  // Older clients select Windows assets by x64/arm64 substring; query aliases retain that compatibility.
  writeFile(path.join(outputDirectory, "latest.yml"), legacyLatestYml, "utf8"),
  ...files.map((file) => writeFile(path.join(outputDirectory, `latest-win-${file.architecture}.yml`), createUpdateInfo(file), "utf8")),
]);
