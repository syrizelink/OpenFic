import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const desktopDir = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const frontendDir = path.resolve(desktopDir, "..", "frontend");
const IS_WINDOWS = process.platform === "win32";

function runPnpm(args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn("pnpm", args, { cwd, stdio: "inherit", shell: IS_WINDOWS });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`pnpm ${args.join(" ")} exited with code ${code}`));
    });
  });
}

async function main() {
  console.log("[dev:local] 构建前端 (frontend/dist)...");
  await runPnpm(["build"], frontendDir);
  console.log("[dev:local] 构建桌面端 setup UI 与主进程...");
  await runPnpm(["build:setup"], desktopDir);
  await runPnpm(["build:main"], desktopDir);

  console.log("[dev:local] 启动 Electron（OPENFIC_DEV_MODE=1）...");
  const electronEnv = { ...process.env, OPENFIC_DEV_MODE: "1" };
  delete electronEnv.ELECTRON_RUN_AS_NODE;
  const electronPath =
    process.platform === "win32"
      ? path.join(desktopDir, "node_modules", "electron", "dist", "electron.exe")
      : process.platform === "darwin"
        ? path.join(desktopDir, "node_modules", "electron", "dist", "Electron.app", "Contents", "MacOS", "Electron")
        : path.join(desktopDir, "node_modules", "electron", "dist", "electron");
  const electron = spawn(electronPath, ["."], {
    cwd: desktopDir,
    stdio: "inherit",
    env: electronEnv,
  });

  const stopElectron = () => {
    if (electron.exitCode !== null || electron.signalCode !== null) return;
    if (IS_WINDOWS) {
      spawn("taskkill", ["/F", "/T", "/PID", String(electron.pid)], { stdio: "ignore", windowsHide: true });
      return;
    }
    electron.kill("SIGTERM");
  };
  process.on("SIGINT", stopElectron);
  process.on("SIGTERM", stopElectron);

  electron.on("exit", (code) => process.exit(code ?? 0));
  electron.on("error", (error) => {
    console.error(`[dev:local] 启动 Electron 失败：${error.message}`);
    process.exit(1);
  });
}

main().catch((error) => {
  console.error(`[dev:local] ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
});
