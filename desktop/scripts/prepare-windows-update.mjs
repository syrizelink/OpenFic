import { createHash } from "node:crypto";
import { access, readFile, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";

const outputDirectory = path.resolve(process.argv[2] ?? "dist-electron");
const packageJson = JSON.parse(await readFile(path.resolve("package.json"), "utf8"));
const version = packageJson.version;
const architectures = ["x64", "arm64"];

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
  architectures.map((arch) => getFileInfo(`OpenFic-${version}-${arch}-win-setup.exe`)),
);
const primaryFile = files[0];
const latestYml = [
  `version: ${version}`,
  "files:",
  ...files.flatMap((file) => [`  - url: ${file.fileName}`, `    sha512: ${file.sha512}`, `    size: ${file.size}`]),
  `path: ${primaryFile.fileName}`,
  `sha512: ${primaryFile.sha512}`,
  `releaseDate: '${new Date().toISOString()}'`,
  "",
].join("\n");

await writeFile(path.join(outputDirectory, "latest.yml"), latestYml, "utf8");
