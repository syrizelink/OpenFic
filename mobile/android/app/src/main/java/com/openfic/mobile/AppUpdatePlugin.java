package com.openfic.mobile;

import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import androidx.core.content.FileProvider;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.json.JSONArray;
import org.json.JSONObject;

@CapacitorPlugin(name = "AppUpdate")
public class AppUpdatePlugin extends Plugin {
    private static final String RELEASES = "https://github.com/syrizelink/OpenFic/releases/download/";
    private static final String LATEST = "https://api.github.com/repos/syrizelink/OpenFic/releases/latest";
    private SharedPreferences preferences;
    private DownloadManager downloads;
    private long verifiedId = -1;

    @Override public void load() {
        preferences = getContext().getSharedPreferences("openfic.updates", Context.MODE_PRIVATE);
        downloads = (DownloadManager) getContext().getSystemService(Context.DOWNLOAD_SERVICE);
    }

    @PluginMethod public void check(PluginCall call) {
        getBridge().execute(() -> {
            try {
                JSObject current = status();
                String state = current.getString("status");
                if ("downloading".equals(state) || "ready".equals(state)) {
                    call.resolve(current);
                    return;
                }
                preferences.edit().remove("error").commit();
                String testBaseUrl = BuildConfig.OPENFIC_UPDATE_TEST_BASE_URL;
                if (!testBaseUrl.isEmpty()) {
                    JSONObject testManifest = fetchJson(testBaseUrl + "/android-update.json");
                    if (testManifest == null) {
                        call.resolve(status());
                        return;
                    }
                    validate(testManifest);
                    if (testManifest.getLong("versionCode") <= installedCode()) {
                        call.resolve(status());
                        return;
                    }
                    enqueueTestDownload(testManifest);
                    call.resolve(status());
                    return;
                }
                JSONObject release = fetchJson(LATEST);
                if (release == null || release.optBoolean("draft") || release.optBoolean("prerelease")) {
                    call.resolve(status());
                    return;
                }
                String tag = release.getString("tag_name");
                String version = tag.startsWith("v") ? tag.substring(1) : tag;
                if (UpdatePolicy.versionCode(version) <= installedCode()) {
                    call.resolve(status());
                    return;
                }
                String manifestUrl = RELEASES + "v" + version + "/android-update.json";
                String apkUrl = RELEASES + "v" + version + "/OpenFic-" + version + "-android.apk";
                JSONArray assets = release.getJSONArray("assets");
                boolean hasManifest = false;
                boolean hasApk = false;
                for (int index = 0; index < assets.length(); index++) {
                    String url = assets.getJSONObject(index).optString("browser_download_url");
                    hasManifest |= manifestUrl.equals(url);
                    hasApk |= apkUrl.equals(url);
                }
                // Releases can become visible before their Android artifacts finish uploading.
                if (!hasManifest || !hasApk) {
                    call.resolve(status());
                    return;
                }
                JSONObject manifest = fetchJson(manifestUrl);
                if (manifest == null || !version.equals(manifest.getString("version"))) {
                    throw new Exception("更新清单与 Release 版本不一致。");
                }
                validate(manifest);
                clearDownload();
                File target = apkFile();
                if (!target.getParentFile().isDirectory() && !target.getParentFile().mkdirs()) throw new Exception("无法创建更新下载目录。");
                if (target.exists() && !target.delete()) throw new Exception("无法清理旧安装包。");
                DownloadManager.Request request = new DownloadManager.Request(Uri.parse(apkUrl))
                    .setTitle("OpenFic " + version)
                    .setDescription("正在下载应用更新，完成后请返回 OpenFic 安装。")
                    .setMimeType("application/vnd.android.package-archive")
                    .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE)
                    .setDestinationInExternalFilesDir(getContext(), null, "updates/update.apk")
                    .setAllowedOverMetered(true)
                    .setAllowedOverRoaming(false);
                long id = downloads.enqueue(request);
                preferences.edit().putString("manifest", manifest.toString()).putLong("downloadId", id).remove("error").commit();
                call.resolve(status());
            } catch (Exception error) {
                fail("检查更新失败：" + error.getMessage());
                call.resolve(errorStatus());
            }
        });
    }

    @PluginMethod public void getStatus(PluginCall call) {
        getBridge().execute(() -> {
            try { call.resolve(status()); }
            catch (Exception error) {
                fail(error.getMessage());
                call.resolve(errorStatus());
            }
        });
    }

    @PluginMethod public void install(PluginCall call) {
        getBridge().execute(() -> {
            try {
                if (!"ready".equals(status().getString("status"))) throw new Exception("安装包尚未下载完成，请重试。");
                verify(new JSONObject(preferences.getString("manifest", "{}")));
                getActivity().runOnUiThread(() -> {
                    try {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !getContext().getPackageManager().canRequestPackageInstalls()) {
                            Intent settings = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                Uri.parse("package:" + getContext().getPackageName()));
                            getActivity().startActivity(settings);
                            JSObject result = new JSObject();
                            result.put("permissionRequired", true);
                            call.resolve(result);
                            return;
                        }
                        Uri uri = FileProvider.getUriForFile(getContext(), getContext().getPackageName() + ".fileprovider", apkFile());
                        Intent install = new Intent(Intent.ACTION_VIEW)
                            .setDataAndType(uri, "application/vnd.android.package-archive")
                            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        getActivity().startActivity(install);
                        JSObject result = new JSObject();
                        result.put("permissionRequired", false);
                        call.resolve(result);
                    } catch (Exception error) { call.reject("无法打开安装界面：" + error.getMessage()); }
                });
            } catch (Exception error) {
                fail(error.getMessage());
                call.reject(error.getMessage());
            }
        });
    }

    private JSObject status() throws Exception {
        String saved = preferences.getString("manifest", null);
        long id = preferences.getLong("downloadId", -1);
        if (saved == null || id == -1) return errorStatus();
        JSONObject manifest = new JSONObject(saved);
        validate(manifest);
        if (manifest.getLong("versionCode") <= installedCode()) {
            clearDownload();
            preferences.edit().remove("error").commit();
            return errorStatus();
        }
        JSObject result = new JSObject();
        result.put("version", manifest.getString("version"));
        result.put("currentVersion", installed().versionName);
        try (Cursor cursor = downloads.query(new DownloadManager.Query().setFilterById(id))) {
            if (cursor == null || !cursor.moveToFirst()) throw new Exception("下载记录已丢失，请重新检查更新。");
            int state = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
            if (state == DownloadManager.STATUS_FAILED) throw new Exception("安装包下载失败，请检查网络和存储空间后重试。");
            if (state == DownloadManager.STATUS_SUCCESSFUL) {
                if (verifiedId != id) {
                    verify(manifest);
                    verifiedId = id;
                }
                result.put("status", "ready");
                result.put("progress", 100);
            } else {
                long received = cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));
                long total = manifest.getLong("size");
                result.put("status", "downloading");
                result.put("progress", Math.min(99, Math.max(0, received * 100 / total)));
                result.put("message", state == DownloadManager.STATUS_PAUSED ? "下载已暂停，网络恢复后将自动继续。" : "安装包正在自动下载，可继续使用应用。");
            }
        }
        return result;
    }

    private void validate(JSONObject manifest) throws Exception {
        UpdatePolicy.validate(manifest.getString("version"), manifest.getLong("versionCode"),
            manifest.getString("url"), manifest.getString("sha256"), manifest.getLong("size"),
            BuildConfig.OPENFIC_UPDATE_TEST_BASE_URL);
    }

    private void enqueueTestDownload(JSONObject manifest) throws Exception {
        String version = manifest.getString("version");
        clearDownload();
        File target = apkFile();
        if (!target.getParentFile().isDirectory() && !target.getParentFile().mkdirs()) {
            throw new Exception("Cannot create the update download directory.");
        }
        if (target.exists() && !target.delete()) throw new Exception("Cannot remove the previous update package.");
        DownloadManager.Request request = new DownloadManager.Request(Uri.parse(manifest.getString("url")))
            .setTitle("OpenFic " + version)
            .setDescription("Downloading app update. Return to OpenFic to install.")
            .setMimeType("application/vnd.android.package-archive")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE)
            .setDestinationInExternalFilesDir(getContext(), null, "updates/update.apk")
            .setAllowedOverMetered(true)
            .setAllowedOverRoaming(false);
        long id = downloads.enqueue(request);
        preferences.edit().putString("manifest", manifest.toString()).putLong("downloadId", id).remove("error").commit();
        verifiedId = -1;
    }

    @SuppressWarnings("deprecation")
    private void verify(JSONObject manifest) throws Exception {
        validate(manifest);
        File file = apkFile();
        if (!UpdatePolicy.matches(file, manifest.getString("sha256"), manifest.getLong("size"))) {
            throw new Exception("安装包完整性校验失败，请重新下载。");
        }
        PackageManager manager = getContext().getPackageManager();
        PackageInfo archive = manager.getPackageArchiveInfo(file.getAbsolutePath(), PackageManager.GET_SIGNATURES);
        PackageInfo local = manager.getPackageInfo(getContext().getPackageName(), PackageManager.GET_SIGNATURES);
        if (archive == null || !local.packageName.equals(archive.packageName)
            || archive.versionCode != manifest.getLong("versionCode") || !manifest.getString("version").equals(archive.versionName)
            || archive.versionCode <= installedCode()) throw new Exception("安装包的应用或版本信息不匹配。");
        if (archive.signatures == null || local.signatures == null || archive.signatures.length == 0
            || !Arrays.equals(archive.signatures, local.signatures)) {
            throw new Exception("安装包签名不匹配。测试版不能直接升级到正式版，请安装同一签名渠道的版本。");
        }
    }

    private PackageInfo installed() throws PackageManager.NameNotFoundException {
        return getContext().getPackageManager().getPackageInfo(getContext().getPackageName(), 0);
    }

    @SuppressWarnings("deprecation")
    private long installedCode() throws PackageManager.NameNotFoundException { return installed().versionCode; }

    private File apkFile() {
        File directory = getContext().getExternalFilesDir(null);
        if (directory == null) throw new IllegalStateException("应用存储不可用。");
        return new File(directory, "updates/update.apk");
    }

    private void clearDownload() {
        long id = preferences.getLong("downloadId", -1);
        if (id != -1) downloads.remove(id);
        preferences.edit().remove("downloadId").remove("manifest").commit();
        verifiedId = -1;
    }

    private void fail(String message) {
        clearDownload();
        preferences.edit().putString("error", message == null ? "更新失败，请重试。" : message).commit();
    }

    private JSObject errorStatus() {
        JSObject result = new JSObject();
        String error = preferences.getString("error", null);
        result.put("status", error == null ? "idle" : "error");
        result.put("message", error == null ? "当前没有可用的 Android 更新。" : error);
        try { result.put("currentVersion", installed().versionName); }
        catch (Exception ignored) { /* The current package is always expected to exist. */ }
        return result;
    }

    private JSONObject fetchJson(String address) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(address).openConnection();
        try {
            connection.setConnectTimeout(15000);
            connection.setReadTimeout(15000);
            connection.setRequestProperty("Accept", address.equals(LATEST) ? "application/vnd.github+json" : "application/json");
            connection.setRequestProperty("User-Agent", "OpenFic-Android");
            int code = connection.getResponseCode();
            if (code == 404) return null;
            if (code != 200 || !isAllowedUpdateResponse(address, connection.getURL())) throw new Exception("更新服务器返回 " + code + "。");
            try (InputStream input = connection.getInputStream(); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    output.write(buffer, 0, count);
                    if (output.size() > 1048576) throw new Exception("更新信息超过大小限制。");
                }
                return new JSONObject(output.toString(StandardCharsets.UTF_8.name()));
            }
        } finally { connection.disconnect(); }
    }

    private boolean isAllowedUpdateResponse(String address, URL responseUrl) {
        if ("https".equals(responseUrl.getProtocol())) return true;
        String testBaseUrl = BuildConfig.OPENFIC_UPDATE_TEST_BASE_URL;
        return !testBaseUrl.isEmpty()
            && "http".equals(responseUrl.getProtocol())
            && address.startsWith(testBaseUrl + "/")
            && responseUrl.toExternalForm().startsWith(testBaseUrl + "/");
    }
}
