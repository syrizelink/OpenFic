import { spawn, spawnSync } from "node:child_process";
import { constants } from "node:fs";
import { access, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createServer } from "vite";

const root = fileURLToPath(new URL("../", import.meta.url));
const port = Number(process.env.MOBILE_DEV_PORT || 5173);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error("MOBILE_DEV_PORT must be a valid TCP port");
}

function javaExecutable(home) {
  return path.join(home, "bin", process.platform === "win32" ? "java.exe" : "java");
}

async function findJava21() {
  const sdkRoot = process.env.ANDROID_HOME || process.env.ANDROID_SDK_ROOT;
  const candidates = [
    process.env.MOBILE_JDK_HOME,
    sdkRoot ? path.join(sdkRoot, "jdk-21") : undefined,
    process.env.JAVA_HOME,
  ].filter((candidate, index, all) => candidate && all.indexOf(candidate) === index);

  for (const home of candidates) {
    const executable = javaExecutable(home);
    try {
      await access(executable, process.platform === "win32" ? 0 : constants.X_OK);
      const result = spawnSync(executable, ["-version"], { encoding: "utf8" });
      const output = `${result.stdout ?? ""}\n${result.stderr ?? ""}`;
      const major = output.match(/version\s+"(?:1\.)?(\d+)/)?.[1];
      if (result.status === 0 && Number(major) === 21) return home;
    } catch {
      // Try the next configured JDK location.
    }
  }

  throw new Error(
    "Android development requires JDK 21. Set MOBILE_JDK_HOME to its folder, or install it at ANDROID_HOME\\jdk-21.",
  );
}

async function hasGradleDistribution(home, distributionName, version) {
  if (!home) return false;
  const distributionRoot = path.join(home, "wrapper", "dists", distributionName);
  const gradleExecutable = path.join(
    `gradle-${version}`,
    "bin",
    process.platform === "win32" ? "gradle.bat" : "gradle",
  );
  try {
    for (const entry of await readdir(distributionRoot, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      await access(path.join(distributionRoot, entry.name, gradleExecutable));
      return true;
    }
  } catch {
    return false;
  }
  return false;
}

function runAdb(adb, args, env) {
  const result = spawnSync(adb, args, { encoding: "utf8", env });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(result.stderr?.trim() || `adb ${args.join(" ")} failed`);
  }
  return result.stdout.trim();
}

async function getAdbPath(env) {
  const sdkRoot = env.ANDROID_HOME || env.ANDROID_SDK_ROOT;
  const sdkAdb = sdkRoot
    ? path.join(sdkRoot, "platform-tools", process.platform === "win32" ? "adb.exe" : "adb")
    : undefined;
  if (sdkAdb) {
    try {
      await access(sdkAdb);
      return sdkAdb;
    } catch {
      // Fall back to adb from PATH.
    }
  }
  return process.platform === "win32" ? "adb.exe" : "adb";
}

function findRequestedTarget(args) {
  const index = args.indexOf("--target");
  if (index !== -1) return args[index + 1];
  return args.find((arg) => arg.startsWith("--target="))?.slice("--target=".length);
}

function listConnectedDevices(adb, env) {
  const output = runAdb(adb, ["devices"], env);
  return output
    .split(/\r?\n/)
    .map((line) => line.trim().split(/\s+/))
    .filter((parts) => parts.length > 1 && parts[1] === "device")
    .map(([serial]) => serial);
}

function getEmulatorPath(env) {
  const sdkRoot = env.ANDROID_HOME || env.ANDROID_SDK_ROOT;
  return sdkRoot
    ? path.join(sdkRoot, "emulator", process.platform === "win32" ? "emulator.exe" : "emulator")
    : process.platform === "win32"
      ? "emulator.exe"
      : "emulator";
}

function listAvailableAvds(emulator, env) {
  const result = spawnSync(emulator, ["-list-avds"], {
    encoding: "utf8",
    env,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(result.stderr?.trim() || "Could not list Android emulators");
  }
  return result.stdout
    .split(/\r?\n/)
    .map((name) => name.trim())
    .filter(Boolean);
}

async function startEmulatorIfNeeded(adb, env, args) {
  const connectedDevices = listConnectedDevices(adb, env);
  if (findRequestedTarget(args)) return;
  if (connectedDevices.length === 1) return connectedDevices[0];
  if (connectedDevices.length > 1) {
    return;
  }

  const emulator = getEmulatorPath(env);
  const avds = listAvailableAvds(emulator, env);
  const requestedAvd = env.MOBILE_ANDROID_AVD?.trim();
  const avd = requestedAvd
    ? avds.find((name) => name === requestedAvd)
    : (avds.find((name) => name.includes("OpenFic")) ?? (avds.length === 1 ? avds[0] : undefined));

  if (!avd) {
    const available = avds.length ? avds.join(", ") : "none";
    throw new Error(
      requestedAvd
        ? `Android emulator ${requestedAvd} was not found. Available emulators: ${available}.`
        : `No Android device is connected and an emulator could not be selected. Available emulators: ${available}. Set MOBILE_ANDROID_AVD to choose one.`,
    );
  }

  console.log(`No Android device is connected. Starting emulator ${avd}...`);
  const emulatorProcess = spawn(emulator, ["-avd", avd], {
    detached: true,
    env,
    stdio: "ignore",
    windowsHide: false,
  });
  await new Promise((resolve, reject) => {
    emulatorProcess.once("error", reject);
    emulatorProcess.once("spawn", resolve);
  });
  emulatorProcess.unref();

  const timeoutMs = 4 * 60 * 1000;
  const deadline = Date.now() + timeoutMs;
  let nextProgressAt = Date.now() + 15000;
  console.log("Waiting for Android to finish booting...");
  while (Date.now() < deadline) {
    const device = listConnectedDevices(adb, env).find((serial) => serial.startsWith("emulator-"));
    if (device) {
      const result = spawnSync(adb, ["-s", device, "shell", "getprop", "sys.boot_completed"], {
        encoding: "utf8",
        env,
      });
      if (result.status === 0 && result.stdout.trim() === "1") {
        console.log(`Android emulator ${device} is ready.`);
        return device;
      }
    }

    if (Date.now() >= nextProgressAt) {
      console.log("Still waiting for Android to finish booting...");
      nextProgressAt = Date.now() + 15000;
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }

  throw new Error(
    `Android emulator ${avd} did not finish booting within ${timeoutMs / 1000} seconds.`,
  );
}

function forwardVitePort(adb, env, args, port) {
  const devices = listConnectedDevices(adb, env);
  const requestedTarget = findRequestedTarget(args);
  const targets = requestedTarget
    ? devices.filter((serial) => serial === requestedTarget)
    : devices;
  if (targets.length === 0) {
    throw new Error(
      requestedTarget
        ? `Android target ${requestedTarget} is not connected. Run adb devices to list connected devices.`
        : "No Android device is connected. Start an emulator or connect a device, then try again.",
    );
  }

  const newlyForwarded = [];
  for (const target of targets) {
    const rules = runAdb(adb, ["-s", target, "reverse", "--list"], env)
      .split(/\r?\n/)
      .map((line) => line.trim().split(/\s+/));
    const rule = rules.find((parts) => parts.at(-2) === `tcp:${port}`);
    if (rule && rule.at(-1) !== `tcp:${port}`) {
      throw new Error(`Device ${target} already forwards tcp:${port} to ${rule.at(-1)}.`);
    }
    if (!rule) {
      runAdb(adb, ["-s", target, "reverse", `tcp:${port}`, `tcp:${port}`], env);
      newlyForwarded.push(target);
    }
    console.log(`Forwarded mobile Vite port ${port} to ${target}`);
  }
  return newlyForwarded;
}

const javaHome = await findJava21();
const wrapperProperties = await readFile(
  path.join(root, "android", "gradle", "wrapper", "gradle-wrapper.properties"),
  "utf8",
);
const distributionName = wrapperProperties.match(/\/(gradle-[^/]+)\.zip/)?.[1];
const gradleVersion = distributionName?.match(/^gradle-(\d+(?:\.\d+)+)-/)?.[1];
if (!distributionName || !gradleVersion) {
  throw new Error(
    "Could not determine the Gradle wrapper distribution from gradle-wrapper.properties",
  );
}

const androidConfigPath = path.join(
  root,
  "android",
  "app",
  "src",
  "main",
  "assets",
  "capacitor.config.json",
);
const originalCapacitorConfig = await readFile(androidConfigPath);

const viteServer = await createServer({
  configFile: path.join(root, "vite.config.ts"),
  server: { host: "127.0.0.1", port, strictPort: true },
});
await viteServer.listen();
viteServer.printUrls();

const capacitorCli = path.join(root, "node_modules", "@capacitor", "cli", "bin", "capacitor");
const childEnv = { ...process.env, JAVA_HOME: javaHome };
if (!childEnv.ANDROID_USER_HOME && childEnv.USERPROFILE) {
  childEnv.ANDROID_USER_HOME = path.join(childEnv.USERPROFILE, ".android");
}
const pathKey = Object.keys(childEnv).find((key) => key.toLowerCase() === "path") ?? "PATH";
childEnv[pathKey] = [path.join(javaHome, "bin"), childEnv[pathKey]]
  .filter(Boolean)
  .join(path.delimiter);
const profileGradleHome = process.env.USERPROFILE
  ? path.join(process.env.USERPROFILE, ".gradle")
  : undefined;
const gradleHomeCandidates = [
  process.env.MOBILE_GRADLE_USER_HOME,
  profileGradleHome,
  process.env.GRADLE_USER_HOME,
].filter((candidate, index, all) => candidate && all.indexOf(candidate) === index);
let cachedGradleHome;
for (const candidate of gradleHomeCandidates) {
  if (await hasGradleDistribution(candidate, distributionName, gradleVersion)) {
    cachedGradleHome = candidate;
    break;
  }
}
if (cachedGradleHome) childEnv.GRADLE_USER_HOME = cachedGradleHome;
else if (process.env.MOBILE_GRADLE_USER_HOME) {
  childEnv.GRADLE_USER_HOME = process.env.MOBILE_GRADLE_USER_HOME;
}

let capacitorProcess;
let interrupted = false;
let adbPath;
let newlyForwarded = [];
const forwardSignal = (signal) => {
  interrupted = true;
  capacitorProcess?.kill(signal);
};

try {
  adbPath = await getAdbPath(childEnv);
  const autoTarget = await startEmulatorIfNeeded(adbPath, childEnv, process.argv.slice(2));
  newlyForwarded = forwardVitePort(adbPath, childEnv, process.argv.slice(2), port);
  console.log(`Using JDK 21 at ${javaHome}`);
  if (childEnv.GRADLE_USER_HOME) {
    console.log(`Using Gradle cache at ${childEnv.GRADLE_USER_HOME}`);
  }
  console.log("Starting the mobile Android debug app with Vite live reload...");
  capacitorProcess = spawn(
    process.execPath,
    [
      capacitorCli,
      "run",
      "android",
      "--no-sync",
      "--live-reload",
      "--host",
      "localhost",
      "--port",
      String(port),
      ...(autoTarget ? ["--target", autoTarget] : []),
      ...process.argv.slice(2),
    ],
    { cwd: root, env: childEnv, stdio: "inherit" },
  );

  process.once("SIGINT", forwardSignal);
  process.once("SIGTERM", forwardSignal);

  const result = await new Promise((resolve, reject) => {
    capacitorProcess.once("error", reject);
    capacitorProcess.once("exit", (code, signal) => resolve({ code, signal }));
  });
  process.exitCode = interrupted ? 0 : (result.code ?? 1);
} finally {
  process.removeListener("SIGINT", forwardSignal);
  process.removeListener("SIGTERM", forwardSignal);
  if (capacitorProcess && capacitorProcess.exitCode === null) {
    capacitorProcess.kill("SIGTERM");
  }
  for (const target of newlyForwarded) {
    try {
      runAdb(adbPath, ["-s", target, "reverse", "--remove", `tcp:${port}`], childEnv);
    } catch {
      // The device may have disconnected while the preview was running.
    }
  }
  await viteServer.close();
  await writeFile(androidConfigPath, originalCapacitorConfig);
}
