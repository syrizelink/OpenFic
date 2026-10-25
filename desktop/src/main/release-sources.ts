import type { UpdateInfo } from "electron-updater";
import { parseUpdateInfo } from "electron-updater/out/providers/Provider.js";
import type { DownloadSource } from "./source-selection.js";

export interface ReleaseSource extends DownloadSource {
  tagApi: (version: string) => string;
  downloadBase: string;
  releasePage: (version: string) => string;
}

export const RELEASE_SOURCES: readonly ReleaseSource[] = [
  {
    kind: "default",
    url: "https://api.github.com/repos/syrizelink/OpenFic/releases/latest",
    tagApi: (version) => `https://api.github.com/repos/syrizelink/OpenFic/releases/tags/v${encodeURIComponent(version)}`,
    downloadBase: "https://github.com/syrizelink/OpenFic/releases/download/",
    releasePage: (version) => `https://github.com/syrizelink/OpenFic/releases/tag/v${encodeURIComponent(version)}`,
  },
  {
    kind: "mirror",
    url: "https://api.atomgit.com/api/v5/repos/Syrize/OpenFic/releases/latest",
    tagApi: (version) => `https://api.atomgit.com/api/v5/repos/Syrize/OpenFic/releases/v${encodeURIComponent(version)}`,
    downloadBase: "https://atomgit.com/Syrize/OpenFic/releases/download/",
    releasePage: (version) => `https://atomgit.com/Syrize/OpenFic/releases/v${encodeURIComponent(version)}`,
  },
];

export interface ReleaseSnapshot {
  source: ReleaseSource;
  baseUrl: string;
  info: UpdateInfo;
}

export function releaseBaseUrl(source: ReleaseSource, version: string): string {
  return `${source.downloadBase}v${encodeURIComponent(version)}/`;
}

/** Pin retries to the same version, architecture and checksum even if a newer release appears. */
export async function loadReleaseSnapshot(
  source: ReleaseSource,
  architecture: string,
  readText: (url: string) => Promise<string>,
  expected?: UpdateInfo,
): Promise<ReleaseSnapshot> {
  const release = JSON.parse(await readText(expected ? source.tagApi(expected.version) : source.url)) as {
    tag_name?: unknown; body?: unknown; prerelease?: boolean; draft?: boolean;
  };
  if (typeof release.tag_name !== "string" || !/^v\d+\.\d+\.\d+$/.test(release.tag_name) || release.prerelease || release.draft) {
    throw new Error(`Invalid stable release: ${source.url}`);
  }
  const version = release.tag_name.slice(1);
  if (expected && version !== expected.version) throw new Error("Fallback release version does not match");
  const baseUrl = releaseBaseUrl(source, version);
  const channelFile = `latest-win-${architecture}.yml`;
  const metadataUrl = new URL(channelFile, baseUrl);
  const info = parseUpdateInfo(await readText(metadataUrl.href), channelFile, metadataUrl);
  const installer = `OpenFic-${version}-win-${architecture}-setup.exe`;
  if (info?.version !== version || !Array.isArray(info.files) || info.files.length !== 1) {
    throw new Error(`Invalid update metadata: ${metadataUrl.href}`);
  }
  const file = info.files[0];
  if (file.url !== installer || !file.sha512 || (expected && file.sha512 !== expected.files[0]?.sha512)) {
    throw new Error(`Update artifact or checksum does not match: ${metadataUrl.href}`);
  }
  if (typeof release.body === "string" && release.body.trim()) info.releaseNotes = release.body.trim();
  return { source, baseUrl, info };
}

export function releaseBlockmapUrls(snapshot: ReleaseSnapshot, oldVersion: string): URL[] {
  const newVersion = snapshot.info.version;
  const fileName = snapshot.info.files[0].url;
  return [
    new URL(`${fileName.replace(newVersion, oldVersion)}.blockmap`, releaseBaseUrl(snapshot.source, oldVersion)),
    new URL(`${fileName}.blockmap`, snapshot.baseUrl),
  ];
}
