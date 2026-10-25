import { app, shell, type BrowserWindow } from "electron";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import electronUpdater, { CancellationToken, NsisUpdater, type AppUpdater, type ProgressInfo, type UpdateInfo } from "electron-updater";
import { IpcChannels, type UpdateState } from "../shared/ipc.js";
import { getUpdateArchitectureName, isAutoUpdateSupported } from "./update-support.js";
import { configureSystemProxy } from "./proxy.js";
import { GenericProvider } from "electron-updater/out/providers/GenericProvider.js";
import type { ProviderRuntimeOptions } from "electron-updater/out/providers/Provider.js";
import { fetchSourceText, getDownloadSourcePreference, orderDownloadSources, probeDownloadUrl } from "./download-sources.js";
import { loadReleaseSnapshot, RELEASE_SOURCES, releaseBaseUrl, releaseBlockmapUrls, type ReleaseSnapshot, type ReleaseSource } from "./release-sources.js";
import { appendLog } from "./logging.js";

const { autoUpdater } = electronUpdater;

let shellWindow: BrowserWindow | null = null;
let updateState: UpdateState = { status: "idle" };
let initialized = false;
let downloadCancellationToken: CancellationToken | null = null;
let busy = false;
let localUpdateFeed = false;
let selectedRelease: ReleaseSnapshot | null = null;

function publishState(nextState: UpdateState): void {
  updateState = nextState;
  shellWindow?.webContents.send(IpcChannels.updateState, nextState);
}

function describeError(error: Error): string {
  return error.message || "更新服务暂时不可用";
}

function isMissingUpdateMetadataError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return message.includes(`${autoUpdater.channel}.yml`) && /\b404\b/.test(message);
}

function getUpdaterReleaseNotes(info: UpdateInfo): string | undefined {
  if (typeof info.releaseNotes === "string") return info.releaseNotes.trim() || undefined;
  if (!Array.isArray(info.releaseNotes)) return undefined;
  const notes = info.releaseNotes
    .map((item) => item.note?.trim())
    .filter((item): item is string => Boolean(item));
  return notes.length ? notes.join("\n\n") : undefined;
}

const readUpdateText = (url: string) => fetchSourceText(url, autoUpdater.netSession.fetch.bind(autoUpdater.netSession));

/** Supply validated metadata and retain the upstream downloader's checksum and installer checks. */
function useRelease(snapshot: ReleaseSnapshot): void {
  class ReleaseProvider extends GenericProvider {
    constructor(_options: unknown, updater: AppUpdater, runtimeOptions: ProviderRuntimeOptions) {
      super({ provider: "generic", url: snapshot.baseUrl, useMultipleRangeRequest: false }, updater, {
        ...runtimeOptions, isUseMultipleRangeRequest: false,
      });
    }

    override async getLatestVersion(): Promise<UpdateInfo> { return snapshot.info; }

    override async getBlockMapFiles(_baseUrl: URL, oldVersion: string): Promise<URL[]> {
      const preference = await getDownloadSourcePreference();
      return Promise.all([0, 1].map(async (index) => {
        const reachable = new Set<string>();
        const candidates = RELEASE_SOURCES.map((source) => {
          const candidate = { ...snapshot, source, baseUrl: releaseBaseUrl(source, snapshot.info.version) };
          return { kind: source.kind, url: releaseBlockmapUrls(candidate, oldVersion)[index].href };
        });
        const probe = async ({ url }: { url: string }) => {
          await probeDownloadUrl(url);
          reachable.add(url);
        };
        const ordered = await orderDownloadSources(candidates, preference, probe);
        for (const candidate of ordered) {
          try {
            if (!reachable.has(candidate.url)) await probe(candidate);
            return new URL(candidate.url);
          } catch (error) {
            appendLog("runtime", `blockmap source unavailable: ${describeError(error instanceof Error ? error : new Error(String(error)))}`);
          }
        }
        // If both sources fail the updater falls back to a full installer.
        return releaseBlockmapUrls(snapshot, oldVersion)[index];
      }));
    }
  }
  autoUpdater.setFeedURL({ provider: "custom", updateProvider: ReleaseProvider });
  selectedRelease = snapshot;
}

async function getReleaseCandidates(expected?: UpdateInfo, forDownload = false): Promise<{
  sources: ReleaseSource[];
  load: (source: ReleaseSource) => Promise<ReleaseSnapshot>;
}> {
  const snapshots = new Map<ReleaseSource, Promise<ReleaseSnapshot>>();
  const load = (source: ReleaseSource) => {
    let snapshot = snapshots.get(source);
    if (!snapshot) {
      const architecture = getUpdateArchitectureName({ platform: process.platform, arch: process.arch });
      if (!architecture) throw new Error("Unsupported update architecture");
      snapshot = loadReleaseSnapshot(source, architecture, readUpdateText, expected);
      snapshots.set(source, snapshot);
      void snapshot.catch(() => snapshots.delete(source));
    }
    return snapshot;
  };
  const sources = await orderDownloadSources(RELEASE_SOURCES, await getDownloadSourcePreference(), async (source) => {
    const snapshot = await load(source);
    if (forDownload) await probeDownloadUrl(new URL(snapshot.info.files[0].url, snapshot.baseUrl).href);
  });
  return { sources, load };
}

function onDownloadProgress(progress: ProgressInfo): void {
  if (downloadCancellationToken?.cancelled) return;
  publishState({
    ...updateState,
    status: "downloading",
    progress: progress.percent / 100,
    transferred: progress.transferred,
    total: progress.total,
    bytesPerSecond: progress.bytesPerSecond,
  });
}

function canUseAutoUpdater(): boolean {
  if (!app.isPackaged) return false;
  return isAutoUpdateSupported({
    platform: process.platform,
    arch: process.arch,
  });
}

function configurePortableInstallDirectory(): void {
  const installDirectory = path.dirname(app.getPath("exe"));
  const uninstallerPath = path.join(installDirectory, "Uninstall OpenFic.exe");
  if (!existsSync(uninstallerPath) && autoUpdater instanceof NsisUpdater) {
    autoUpdater.installDirectory = installDirectory;
  }
}

export async function initializeUpdater(window: BrowserWindow): Promise<void> {
  shellWindow = window;
  await configureSystemProxy(autoUpdater.netSession);
  if (initialized) {
    window.webContents.send(IpcChannels.updateState, updateState);
    return;
  }

  initialized = true;
  if (!canUseAutoUpdater()) {
    publishState({ status: "unsupported" });
    return;
  }

  const updateArchitecture = getUpdateArchitectureName({ platform: process.platform, arch: process.arch });
  if (!updateArchitecture) {
    publishState({ status: "unsupported" });
    return;
  }

  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = false;
  autoUpdater.channel = `latest-win-${updateArchitecture}`;
  autoUpdater.allowDowngrade = false;
  configurePortableInstallDirectory();
  try {
    // Preserve packaged localhost update testing.
    const config = readFileSync(path.join(process.resourcesPath, "app-update.yml"), "utf8");
    localUpdateFeed = /^provider:\s*generic\s*$/m.test(config) && /^url:\s*http:\/\/127\.0\.0\.1(?::\d+)?\s*$/m.test(config);
  } catch { /* Production feeds are resolved explicitly. */ }
  autoUpdater.on("download-progress", onDownloadProgress);
  autoUpdater.on("update-downloaded", (info) => publishState({ status: "downloaded", version: info.version, releaseNotes: getUpdaterReleaseNotes(info) }));
  // Report failures only after both sources have failed, without intermediate error flicker.
  autoUpdater.on("error", (error) => appendLog("runtime", `Desktop update: ${describeError(error)}`));
  publishState({ status: "idle" });
}

export function getUpdateState(): UpdateState {
  return updateState;
}

export async function checkForUpdates(): Promise<void> {
  if (!canUseAutoUpdater()) { publishState({ status: "unsupported" }); return; }
  if (busy || updateState.status === "downloaded") return;
  busy = true;
  publishState({ status: "checking" });
  try {
    const candidates = localUpdateFeed ? null : await getReleaseCandidates();
    const errors: unknown[] = [];
    for (const source of candidates?.sources ?? [null]) {
      try {
        if (source && candidates) useRelease(await candidates.load(source));
        const result = await autoUpdater.checkForUpdates();
        if (!result) throw new Error("Update service returned no version information");
        publishState(result.isUpdateAvailable
          ? { status: "available", version: result.updateInfo.version, releaseNotes: getUpdaterReleaseNotes(result.updateInfo) }
          : { status: "not-available" });
        return;
      } catch (error) {
        errors.push(error);
        appendLog("runtime", `Update source check failed: ${String(error)}`);
      }
    }
    if (errors.length && errors.every(isMissingUpdateMetadataError)) {
      publishState({ status: "not-available" });
      return;
    }
    throw new Error(errors.map(String).join("\n"));
  } catch (error) {
    publishState({ status: "error", message: String(error) });
  } finally { busy = false; }
}

export async function downloadUpdate(): Promise<void> {
  if (busy || updateState.status !== "available") return;
  busy = true;
  const availableState = { ...updateState };
  const expected = selectedRelease?.info;
  const token = new CancellationToken();
  downloadCancellationToken = token;
  publishState({ ...availableState, status: "downloading", progress: 0, transferred: 0 });
  try {
    const candidates = localUpdateFeed ? null : await getReleaseCandidates(expected, true);
    const errors: unknown[] = [];
    for (const source of candidates?.sources ?? [null]) {
      if (token.cancelled) break;
      try {
        if (source && candidates) {
          useRelease(await candidates.load(source));
          const result = await autoUpdater.checkForUpdates();
          if (!result?.isUpdateAvailable || result.updateInfo.version !== availableState.version) throw new Error("Update version changed; check for updates again");
        }
        if (token.cancelled) break;
        publishState({ ...availableState, status: "downloading", progress: 0, transferred: 0 });
        await autoUpdater.downloadUpdate(token);
        return;
      } catch (error) {
        if (token.cancelled) break;
        errors.push(error);
        appendLog("runtime", `Update download failed, trying fallback: ${String(error)}`);
      }
    }
    if (!token.cancelled) throw new Error(errors.map(String).join("\n"));
  } catch (error) {
    if (!token.cancelled) publishState({ status: "error", message: String(error) });
  } finally {
    if (token.cancelled) publishState(availableState);
    downloadCancellationToken = null;
    busy = false;
  }
}

export function cancelUpdateDownload(): void {
  if (updateState.status !== "downloading") return;
  downloadCancellationToken?.cancel();
}

export function installUpdate(): void {
  if (updateState.status !== "downloaded") return;
  autoUpdater.quitAndInstall(false, true);
}

export async function openUpdateRelease(): Promise<void> {
  if (!updateState.version) return;
  await shell.openExternal((selectedRelease?.source ?? RELEASE_SOURCES[0]).releasePage(updateState.version));
}
