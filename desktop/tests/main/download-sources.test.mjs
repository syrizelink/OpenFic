import assert from "node:assert/strict";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";
import { orderDownloadSources } from "../../dist/main/source-selection.js";
import { resolvePythonAsset } from "../../dist/main/runtime/python-assets.js";
import { loadReleaseSnapshot, RELEASE_SOURCES, releaseBlockmapUrls } from "../../dist/main/release-sources.js";

const sources = [{ kind: "default", url: "default" }, { kind: "mirror", url: "mirror" }];

test("explicit preference tries that source first without probing or losing the fallback", async () => {
  for (const preference of ["default", "mirror"]) {
    const ordered = await orderDownloadSources(sources, preference, () => { throw new Error("Must not probe"); });
    assert.equal(ordered[0].kind, preference);
    assert.equal(ordered.length, 2);
  }
});

test("auto orders successful probes by completion time, retaining unavailable fallbacks", async () => {
  const ordered = await orderDownloadSources(sources, "auto", async ({ kind }) => delay(kind === "default" ? 30 : 1));
  assert.equal(ordered[0].kind, "mirror");
  const failed = await orderDownloadSources(sources, "auto", async ({ kind }) => {
    if (kind === "mirror") throw new Error("offline");
  });
  assert.deepEqual(failed, sources);
  assert.deepEqual(await orderDownloadSources(sources, "auto", async () => { throw new Error("offline"); }), sources);
});

test("all supported Python targets use exactly GitHub and Aliyun with identical filenames", () => {
  for (const [platform, arch] of [["win32", "x64"], ["linux", "x64"], ["darwin", "arm64"], ["darwin", "x64"]]) {
    const { urls } = resolvePythonAsset(platform, arch);
    assert.equal(urls.length, 2);
    assert.equal(new URL(urls[0]).host, "github.com");
    assert.equal(new URL(urls[1]).host, "mirrors.aliyun.com");
    assert.equal(urls[0].split("/").at(-1), urls[1].split("/").at(-1));
  }
});

function fixture(source, overrides = {}, metadataOverrides = {}) {
  const version = "0.12.2";
  const metadata = { version, files: [{ url: `OpenFic-${version}-win-x86_64-setup.exe`, sha512: "checksum", size: 123 }], ...metadataOverrides };
  const requests = [];
  return {
    requests,
    read: async (url) => {
      requests.push(url);
      return JSON.stringify(url.endsWith(".yml") ? metadata : { tag_name: `v${version}`, body: "Release notes", ...overrides });
    },
    source,
  };
}

test("both release APIs supply metadata and notes, without retaining redirect CDN URLs", async () => {
  for (const source of RELEASE_SOURCES) {
    const { requests, read } = fixture(source);
    const snapshot = await loadReleaseSnapshot(source, "x86_64", read);
    assert.equal(snapshot.info.releaseNotes, "Release notes");
    assert.equal(requests[0], source.url);
    assert.equal(requests[1], `${source.downloadBase}v0.12.2/latest-win-x86_64.yml`);
    const maps = releaseBlockmapUrls(snapshot, "0.12.1");
    assert.equal(maps[0].href, `${source.downloadBase}v0.12.1/OpenFic-0.12.1-win-x86_64-setup.exe.blockmap`);
    assert.equal(maps[1].href, `${source.downloadBase}v0.12.2/OpenFic-0.12.2-win-x86_64-setup.exe.blockmap`);
  }
});

test("fallback requests the pinned release and rejects mismatched checksum, version or architecture", async () => {
  const expected = { version: "0.12.2", files: [{ sha512: "checksum" }] };
  const source = RELEASE_SOURCES[1];
  const good = fixture(source);
  await loadReleaseSnapshot(source, "x86_64", good.read, expected);
  assert.equal(good.requests[0], source.tagApi(expected.version));
  for (const [release, metadata] of [
    [{ tag_name: "v0.12.3" }, {}],
    [{ prerelease: true }, {}],
    [{}, { version: "0.12.3" }],
    [{}, { files: [{ url: "OpenFic-0.12.2-win-aarch64-setup.exe", sha512: "checksum" }] }],
    [{}, { files: [{ url: "OpenFic-0.12.2-win-x86_64-setup.exe", sha512: "other" }] }],
  ]) {
    await assert.rejects(loadReleaseSnapshot(source, "x86_64", fixture(source, release, metadata).read, expected));
  }
});
