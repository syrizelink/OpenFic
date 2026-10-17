import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { test } from "node:test";

import * as updates from "../scripts/android-update.mjs";

test("stable Android versions are ordered and bounded", () => {
  assert.equal(typeof updates.androidVersionCode, "function");
  assert.equal(updates.androidVersionCode("0.12.1"), 12001);
  assert.ok(updates.androidVersionCode("1.0.0") > updates.androidVersionCode("0.999.999"));
  for (const version of ["1.0.0-beta.1", "1.1000.0", "1.0.1000", "2101.0.0", "01.2.3"]) {
    assert.throws(() => updates.androidVersionCode(version));
  }
});

test("update metadata identifies the exact official release APK and its bytes", () => {
  assert.equal(typeof updates.createUpdateManifest, "function");
  const apk = Buffer.from("signed APK bytes");
  assert.deepEqual(updates.createUpdateManifest("0.12.2", apk), {
    version: "0.12.2",
    versionCode: 12002,
    url: "https://github.com/syrizelink/OpenFic/releases/download/v0.12.2/OpenFic-0.12.2-android.apk",
    sha256: createHash("sha256").update(apk).digest("hex"),
    size: apk.length,
  });
  assert.throws(() => updates.createUpdateManifest("0.12.2", Buffer.alloc(0)));
});
