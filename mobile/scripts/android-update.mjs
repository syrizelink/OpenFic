import { createHash } from "node:crypto";

export function androidVersionCode(version) {
  if (!/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(version))
    throw new Error("Android releases require a stable major.minor.patch version");
  const [major, minor, patch] = version.split(".").map(Number);
  const code = major * 1_000_000 + minor * 1_000 + patch;
  if (minor > 999 || patch > 999 || code < 1 || code > 2_100_000_000)
    throw new Error("Android version is outside the supported versionCode range");
  return code;
}

export function createUpdateManifest(version, apk) {
  if (!apk.length) throw new Error("Cannot publish an empty APK");
  return {
    version,
    versionCode: androidVersionCode(version),
    url: `https://github.com/syrizelink/OpenFic/releases/download/v${version}/OpenFic-${version}-android.apk`,
    sha256: createHash("sha256").update(apk).digest("hex"),
    size: apk.length,
  };
}
