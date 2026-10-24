import { spawnSync } from "node:child_process";
import { createReadStream } from "node:fs";
import { access, copyFile, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { constants } from "node:fs";
import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { androidVersionCode, createUpdateManifest } from "./android-update.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const androidRoot = path.join(root, "android");
const rawArgs = process.argv.slice(2);
const args = rawArgs[0] === "--" ? rawArgs.slice(1) : rawArgs;

function option(name, fallback) {
  const index = args.indexOf(name);
  if (index !== -1) {
    if (!args[index + 1] || args[index + 1].startsWith("--")) {
      throw new Error("Expected a value after " + name);
    }
    return args[index + 1];
  }
  const inline = args.find((arg) => arg.startsWith(name + "="));
  return inline ? inline.slice(name.length + 1) : fallback;
}

if (args.includes("--help") || args.includes("-h")) {
  console.log("Usage: pnpm update:test [-- --port 8765 --base-url http://10.0.2.2:8765 --device emulator-5554 --no-install]");
  console.log("Builds a separate debug-signed test app and higher-version update APK, then serves the manifest and APK.");
  process.exit(0);
}

const port = Number(option("--port", "8765"));
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("--port must be a valid TCP port");
const bindAddress = option("--bind", "0.0.0.0");
const baseInput = option("--base-url", "http://10.0.2.2:" + port);
const baseParsed = new URL(baseInput);
if (baseParsed.protocol !== "http:" || baseParsed.username || baseParsed.password || baseParsed.pathname !== "/" || baseParsed.search || baseParsed.hash) {
  throw new Error("--base-url must be a plain HTTP origin such as http://10.0.2.2:8765");
}
const basePort = baseParsed.port ? Number(baseParsed.port) : 80;
if (basePort !== port) throw new Error("The port in --base-url must match --port");
if (["localhost", "127.0.0.1", "::1"].includes(baseParsed.hostname.toLowerCase())) {
  throw new Error("Use the emulator host 10.0.2.2 or this computer's LAN IP in --base-url, not localhost");
}
const baseUrl = baseParsed.origin;
const noInstall = args.includes("--no-install");

async function ensurePortAvailable() {
  const probe = createServer();
  await new Promise((resolve, reject) => {
    probe.once("error", reject);
    probe.listen(port, bindAddress, resolve);
  });
  await new Promise((resolve) => probe.close(resolve));
}

try {
  await ensurePortAvailable();
} catch (error) {
  if (error.code === "EADDRINUSE") throw new Error("Port " + port + " is already in use. Stop the existing update-test server first.");
  throw error;
}

for (const arg of args) {
  if (!["--help", "-h", "--no-install"].includes(arg) && !arg.startsWith("--")) continue;
  if (arg.startsWith("--") && !["--port", "--base-url", "--bind", "--device", "--no-install", "--help"].some((name) => arg === name || arg.startsWith(name + "="))) {
    throw new Error("Unknown option: " + arg);
  }
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
    try {
      await access(javaExecutable(home), process.platform === "win32" ? 0 : constants.X_OK);
      const result = spawnSync(javaExecutable(home), ["-version"], { encoding: "utf8" });
      const output = (result.stdout || "") + "\n" + (result.stderr || "");
      const major = output.match(/version\s+"(?:1\.)?(\d+)/)?.[1];
      if (result.status === 0 && Number(major) === 21) return home;
    } catch {
      // Continue through the configured JDK locations.
    }
  }
  throw new Error("Android update testing requires JDK 21. Set MOBILE_JDK_HOME or install JDK 21 under ANDROID_HOME\\jdk-21.");
}

async function hasGradleDistribution(home, distributionName, version) {
  if (!home) return false;
  const distributionRoot = path.join(home, "wrapper", "dists", distributionName);
  const executable = path.join("gradle-" + version, "bin", process.platform === "win32" ? "gradle.bat" : "gradle");
  try {
    for (const entry of await readdir(distributionRoot, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      await access(path.join(distributionRoot, entry.name, executable));
      return true;
    }
  } catch {
    return false;
  }
  return false;
}

function run(command, commandArgs, options = {}) {
  const result = spawnSync(command, commandArgs, { encoding: "utf8", ...options });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error((result.stderr || result.stdout || command + " failed").trim());
  }
  return (result.stdout || "").trim();
}

async function getAdbPath() {
  const sdkRoot = process.env.ANDROID_HOME || process.env.ANDROID_SDK_ROOT;
  const sdkAdb = sdkRoot && path.join(sdkRoot, "platform-tools", process.platform === "win32" ? "adb.exe" : "adb");
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

function findDevice(adb, env) {
  const output = run(adb, ["devices"], { env });
  const devices = output
    .split(/\r?\n/)
    .map((line) => line.trim().split(/\s+/))
    .filter((parts) => parts.length > 1 && parts[1] === "device")
    .map(([serial]) => serial);
  const requested = option("--device");
  if (requested) {
    if (!devices.includes(requested)) throw new Error("Android device " + requested + " is not online. Run adb devices.");
    return requested;
  }
  if (devices.length === 1) return devices[0];
  const emulators = devices.filter((serial) => serial.startsWith("emulator-"));
  if (emulators.length === 1) return emulators[0];
  throw new Error("Choose one connected Android device with --device. Online devices: " + (devices.join(", ") || "none"));
}

function nextPatch(version) {
  const [major, minor, patch] = version.split(".").map(Number);
  if (patch < 999) return major + "." + minor + "." + (patch + 1);
  if (minor < 999) return major + "." + (minor + 1) + ".0";
  return (major + 1) + ".0.0";
}

const childEnv = { ...process.env, JAVA_HOME: await findJava21() };
if (!childEnv.ANDROID_USER_HOME && childEnv.USERPROFILE) childEnv.ANDROID_USER_HOME = path.join(childEnv.USERPROFILE, ".android");
delete childEnv.ANDROID_SDK_HOME;
const pathKey = Object.keys(childEnv).find((key) => key.toLowerCase() === "path") || "PATH";
childEnv[pathKey] = [path.join(childEnv.JAVA_HOME, "bin"), childEnv[pathKey]].filter(Boolean).join(path.delimiter);

console.log("Synchronizing the current mobile and frontend assets before building update-test APKs...");
run("pnpm", ["sync"], {
  cwd: root,
  env: childEnv,
  stdio: "inherit",
  shell: process.platform === "win32",
});

const generatedConfigPath = path.join(androidRoot, "app", "src", "main", "assets", "capacitor.config.json");
const generatedConfig = JSON.parse(await readFile(generatedConfigPath, "utf8"));
if (generatedConfig.server?.url) {
  delete generatedConfig.server;
  await writeFile(generatedConfigPath, JSON.stringify(generatedConfig, null, "\t") + "\n");
  console.log("Removed a stale live-reload URL from the generated Android assets before building the test app.");
}

const wrapperProperties = await readFile(path.join(androidRoot, "gradle", "wrapper", "gradle-wrapper.properties"), "utf8");
const distributionName = wrapperProperties.match(/(gradle-[^/]+)\.zip/)?.[1];
const gradleVersion = distributionName?.match(/^gradle-(\d+(?:\.\d+)+)-/)?.[1];
if (!distributionName || !gradleVersion) throw new Error("Could not determine the Gradle wrapper distribution");
const gradleCandidates = [
  process.env.MOBILE_GRADLE_USER_HOME,
  process.env.USERPROFILE ? path.join(process.env.USERPROFILE, ".gradle") : undefined,
  process.env.GRADLE_USER_HOME,
].filter((candidate, index, all) => candidate && all.indexOf(candidate) === index);
for (const candidate of gradleCandidates) {
  if (await hasGradleDistribution(candidate, distributionName, gradleVersion)) {
    childEnv.GRADLE_USER_HOME = candidate;
    break;
  }
}

const adb = await getAdbPath();
const device = noInstall ? undefined : findDevice(adb, childEnv);
const mobilePackage = JSON.parse(await readFile(path.join(root, "package.json"), "utf8"));
const baselineVersion = mobilePackage.version;
const updateVersion = nextPatch(baselineVersion);
androidVersionCode(baselineVersion);
androidVersionCode(updateVersion);
const outputDirectory = path.join(root, "out", "update-test");
await mkdir(outputDirectory, { recursive: true });
const windows = process.platform === "win32";
const gradleCommand = windows ? "gradlew.bat" : "./gradlew";
const buildOutput = path.join(androidRoot, "app", "build", "outputs", "apk", "updateTest", "app-updateTest.apk");

function buildUpdateTest(version) {
  console.log("Building isolated Android update-test app " + version + "...");
  run(gradleCommand, [
    "assembleUpdateTest",
    "--no-daemon",
    "-PopenficUpdateTestVersion=" + version,
    "-PopenficUpdateTestBaseUrl=" + baseUrl,
  ], { cwd: androidRoot, env: childEnv, stdio: "inherit", shell: windows });
}

buildUpdateTest(baselineVersion);
const baselineApk = path.join(outputDirectory, "baseline.apk");
await copyFile(buildOutput, baselineApk);
let applicationId = "com.openfic.mobile.dev.updatetest";
try {
  const metadata = JSON.parse(await readFile(path.join(path.dirname(buildOutput), "output-metadata.json"), "utf8"));
  applicationId = metadata.applicationId || applicationId;
} catch {
  // The deterministic updateTest application ID is used when older Gradle metadata omits it.
}

buildUpdateTest(updateVersion);
const updateApk = path.join(outputDirectory, "OpenFic-" + updateVersion + "-android-updatetest.apk");
await copyFile(buildOutput, updateApk);
const apkBytes = await readFile(updateApk);
const manifest = {
  ...createUpdateManifest(updateVersion, apkBytes),
  url: baseUrl + "/OpenFic-" + updateVersion + "-android-updatetest.apk",
};
const manifestText = JSON.stringify(manifest, null, 2) + "\n";

let manifestRequestedResolve;
let apkRequestedResolve;
let apkFinishedResolve;
const manifestRequested = new Promise((resolve) => { manifestRequestedResolve = resolve; });
const apkRequested = new Promise((resolve) => { apkRequestedResolve = resolve; });
const apkFinished = new Promise((resolve) => { apkFinishedResolve = resolve; });
let firstApkRequest = true;
const server = createServer((request, response) => {
  const requestUrl = new URL(request.url || "/", "http://127.0.0.1");
  const methodAllowed = request.method === "GET" || request.method === "HEAD";
  if (!methodAllowed) {
    response.writeHead(405, { Allow: "GET, HEAD" }).end();
    return;
  }
  if (requestUrl.pathname === "/android-update.json") {
    console.log(request.method + " /android-update.json");
    manifestRequestedResolve(true);
    response.writeHead(200, {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Length": Buffer.byteLength(manifestText),
      "Cache-Control": "no-store",
    });
    response.end(request.method === "HEAD" ? undefined : manifestText);
    return;
  }
  if (requestUrl.pathname === "/OpenFic-" + updateVersion + "-android-updatetest.apk") {
    console.log(request.method + " " + requestUrl.pathname);
    if (firstApkRequest) {
      firstApkRequest = false;
      apkRequestedResolve(true);
    }
    response.writeHead(200, {
      "Content-Type": "application/vnd.android.package-archive",
      "Content-Length": String(manifest.size),
      "Content-Disposition": "attachment; filename=\"OpenFic-" + updateVersion + "-android-updatetest.apk\"",
      "Cache-Control": "no-store",
    });
    if (request.method === "HEAD") {
      response.end();
      return;
    }
    const stream = createReadStream(updateApk);
    stream.on("error", (error) => {
      console.error("APK stream failed: " + error.message);
      if (!response.headersSent) response.writeHead(500);
      response.end();
    });
    response.on("finish", () => {
      console.log("APK download response completed (" + manifest.size + " bytes)");
      apkFinishedResolve(true);
    });
    stream.pipe(response);
    return;
  }
  if (requestUrl.pathname === "/health") {
    const body = JSON.stringify({ status: "ok", version: updateVersion });
    response.writeHead(200, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) });
    response.end(request.method === "HEAD" ? undefined : body);
    return;
  }
  response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" }).end("Not found");
});

await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(port, bindAddress, resolve);
});

console.log("Update test server: http://" + bindAddress + ":" + port);
console.log("Emulator update URL: " + baseUrl + "/android-update.json");
console.log("Update APK: " + updateApk);
console.log("Test package: " + applicationId + " (" + baselineVersion + " -> " + updateVersion + ")");

if (!noInstall) {
  const adbEnv = childEnv;
  const adbRun = (adbArgs) => run(adb, ["-s", device, ...adbArgs], { env: adbEnv });
  console.log("Resetting only the isolated update-test app on " + device + "...");
  const uninstall = spawnSync(adb, ["-s", device, "uninstall", applicationId], { encoding: "utf8", env: adbEnv });
  if (uninstall.error) throw uninstall.error;
  adbRun(["install", baselineApk]);
  adbRun(["shell", "monkey", "-p", applicationId, "1"]);
  console.log("Opened the baseline app. It should check and download " + updateVersion + " automatically.");
  const waitFor = async (promise, timeoutMs) => {
    let timer;
    const result = await Promise.race([
      promise.then(() => true),
      new Promise((resolve) => { timer = setTimeout(() => resolve(false), timeoutMs); }),
    ]);
    clearTimeout(timer);
    return result;
  };
  const requestedManifest = await waitFor(manifestRequested, 30000);
  if (!requestedManifest) console.log("No manifest request yet; check that the app opened and the emulator can reach " + baseUrl + ".");
  const requestedApk = requestedManifest && await waitFor(apkRequested, 30000);
  if (requestedApk) {
    const completed = await waitFor(apkFinished, 60000);
    if (completed) console.log("The test update APK was served. Return to the app and tap the install button when it is ready.");
    else console.log("APK download is still in progress; leave this server running.");
  }
}

console.log("Keep this terminal running while testing. Press Ctrl+C to stop the update server.");
await new Promise((resolve) => {
  process.once("SIGINT", resolve);
  process.once("SIGTERM", resolve);
});
await new Promise((resolve) => server.close(resolve));
