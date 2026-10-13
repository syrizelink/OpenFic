import { spawnSync } from "node:child_process";
import { mkdir, copyFile, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../", import.meta.url));
const { version } = JSON.parse(await readFile(`${root}/package.json`, "utf8"));
const windows = process.platform === "win32";
const build = spawnSync(windows ? "gradlew.bat" : "./gradlew", ["assembleDebug", "--no-daemon"], {
  cwd: `${root}/android`,
  stdio: "inherit",
  shell: windows,
});
if (build.status !== 0) process.exit(build.status ?? 1);
await mkdir(`${root}/out`, { recursive: true });
const artifact = `${root}/out/OpenFic-${version}-android.apk`;
await copyFile(`${root}/android/app/build/outputs/apk/debug/app-debug.apk`, artifact);
console.log(`APK: ${artifact} (debug signed)`);
