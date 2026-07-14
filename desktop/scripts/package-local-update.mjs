import { spawn } from "node:child_process";

const pnpm = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
const version = process.env.OPENFIC_UPDATE_VERSION;

if (version && !/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/.test(version)) {
  throw new Error(`OPENFIC_UPDATE_VERSION is not a valid semantic version: ${version}`);
}

function run(args) {
  return new Promise((resolve, reject) => {
    const child = spawn(pnpm, args, { shell: process.platform === "win32", stdio: "inherit" });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${pnpm} ${args.join(" ")} exited with code ${code}`));
    });
  });
}

function runNode(args) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, args, { stdio: "inherit" });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`node ${args.join(" ")} exited with code ${code}`));
    });
  });
}

const versionConfig = version ? [`--config.extraMetadata.version=${version}`] : [];

await run(["build"]);
await run([
  "exec",
  "electron-builder",
  "--config",
  "electron-builder.local-update.yml",
  "--win",
  "nsis",
  "--x64",
  "--publish",
  "never",
  ...versionConfig,
]);
await run([
  "exec",
  "electron-builder",
  "--config",
  "electron-builder.local-update.yml",
  "--win",
  "nsis",
  "--arm64",
  "--publish",
  "never",
  ...versionConfig,
]);
await runNode(["scripts/normalize-artifact-names.mjs"]);
await runNode(["scripts/prepare-windows-update.mjs"]);
