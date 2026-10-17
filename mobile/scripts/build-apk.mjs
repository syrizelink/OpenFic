import { spawnSync } from "node:child_process";
import { mkdir, copyFile, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { androidVersionCode, createUpdateManifest } from "./android-update.mjs";
const root = fileURLToPath(new URL("../", import.meta.url));
const { version } = JSON.parse(await readFile(`${root}/package.json`, "utf8"));
androidVersionCode(version);
const release = process.argv.includes("--release");
if (release) {
  for (const name of [
    "ANDROID_KEYSTORE_PATH",
    "ANDROID_KEYSTORE_PASSWORD",
    "ANDROID_KEY_ALIAS",
    "ANDROID_KEY_PASSWORD",
  ]) {
    if (!process.env[name]) throw new Error(`Release signing requires ${name}`);
  }
}
const windows = process.platform === "win32";
const variant = release ? "release" : "debug";
const build = spawnSync(
  windows ? "gradlew.bat" : "./gradlew",
  [release ? "assembleRelease" : "assembleDebug", "--no-daemon"],
  {
    cwd: `${root}/android`,
    stdio: "inherit",
    shell: windows,
  },
);
if (build.status !== 0) process.exit(build.status ?? 1);
await mkdir(`${root}/out`, { recursive: true });
const artifact = `${root}/out/OpenFic-${version}-android${release ? "" : "-debug"}.apk`;
await copyFile(`${root}/android/app/build/outputs/apk/${variant}/app-${variant}.apk`, artifact);
if (release) {
  const manifest = createUpdateManifest(version, await readFile(artifact));
  await writeFile(`${root}/out/android-update.json`, `${JSON.stringify(manifest, null, 2)}\n`);
}
console.log(`APK: ${artifact} (${variant} signed)`);
