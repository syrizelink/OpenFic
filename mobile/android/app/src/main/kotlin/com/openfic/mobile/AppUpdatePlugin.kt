package com.openfic.mobile

import android.app.DownloadManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.database.Cursor
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets

@CapacitorPlugin(name = "AppUpdate")
class AppUpdatePlugin : Plugin() {
    private lateinit var preferences: SharedPreferences
    private lateinit var downloads: DownloadManager
    private var verifiedId: Long = -1

    override fun load() {
        preferences = context.getSharedPreferences("openfic.updates", Context.MODE_PRIVATE)
        downloads = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        handleUpdateIntent(activity.intent)
    }

    override fun handleOnNewIntent(intent: Intent) {
        handleUpdateIntent(intent)
    }

    private fun handleUpdateIntent(intent: Intent?) {
        val action = intent?.action ?: return
        if (action != "com.openfic.mobile.DOWNLOAD_UPDATE" &&
            action != "com.openfic.mobile.INSTALL_UPDATE"
        ) return
        intent.action = null
        bridge.execute {
            try {
                val saved = preferences.getString("manifest", null) ?: return@execute
                val manifest = JSONObject(saved)
                validate(manifest)
                if (action == "com.openfic.mobile.DOWNLOAD_UPDATE") {
                    if (manifest.getLong("versionCode") > installedCode() &&
                        preferences.getLong("downloadId", -1) == -1L
                    ) {
                        enqueueDownload(manifest)
                    }
                } else if (status().getString("status") == "ready") {
                    activity.runOnUiThread { launchInstall() }
                }
            } catch (error: Exception) {
                fail(error.message)
            }
        }
    }

    @PluginMethod
    fun check(call: PluginCall) {
        bridge.execute {
            try {
                val current = status()
                val state = current.getString("status")
                if (state == "downloading" || state == "ready") {
                    call.resolve(current)
                    return@execute
                }
                preferences.edit().remove("error").commit()
                val testBaseUrl = BuildConfig.OPENFIC_UPDATE_TEST_BASE_URL
                if (testBaseUrl.isNotEmpty()) {
                    val testManifest = fetchJson("$testBaseUrl/android-update.json")
                    if (testManifest == null) {
                        call.resolve(status())
                        return@execute
                    }
                    validate(testManifest)
                    if (testManifest.getLong("versionCode") <= installedCode()) {
                        call.resolve(status())
                        return@execute
                    }
                    saveAvailable(testManifest)
                    call.resolve(status())
                    return@execute
                }
                val release = fetchJson(LATEST)
                if (release == null || release.optBoolean("draft") || release.optBoolean("prerelease")) {
                    call.resolve(status())
                    return@execute
                }
                val tag = release.getString("tag_name")
                val version = if (tag.startsWith("v")) tag.substring(1) else tag
                if (UpdatePolicy.versionCode(version) <= installedCode()) {
                    call.resolve(status())
                    return@execute
                }
                val manifestUrl = RELEASES + "v" + version + "/android-update.json"
                val apkUrl = RELEASES + "v" + version + "/OpenFic-" + version + "-android.apk"
                val assets = release.getJSONArray("assets")
                var hasManifest = false
                var hasApk = false
                for (index in 0 until assets.length()) {
                    val url = assets.getJSONObject(index).optString("browser_download_url")
                    hasManifest = hasManifest || manifestUrl == url
                    hasApk = hasApk || apkUrl == url
                }
                if (!hasManifest || !hasApk) {
                    call.resolve(status())
                    return@execute
                }
                val manifest = fetchJson(manifestUrl)
                if (manifest == null || version != manifest.getString("version")) {
                    throw Exception("更新清单与 Release 版本不一致。")
                }
                validate(manifest)
                manifest.put("url", apkUrl)
                saveAvailable(manifest)
                call.resolve(status())
            } catch (error: Exception) {
                fail("检查更新失败:${error.message}")
                call.resolve(errorStatus())
            }
        }
    }

    @PluginMethod
    fun download(call: PluginCall) {
        bridge.execute {
            try {
                val saved = preferences.getString("manifest", null)
                    ?: throw Exception("没有可用的更新。")
                val manifest = JSONObject(saved)
                validate(manifest)
                if (manifest.getLong("versionCode") <= installedCode()) {
                    call.resolve(status())
                    return@execute
                }
                if (preferences.getLong("downloadId", -1) == -1L) enqueueDownload(manifest)
                call.resolve(status())
            } catch (error: Exception) {
                fail(error.message)
                call.resolve(errorStatus())
            }
        }
    }

    @PluginMethod
    fun getStatus(call: PluginCall) {
        bridge.execute {
            try {
                call.resolve(status())
            } catch (error: Exception) {
                fail(error.message)
                call.resolve(errorStatus())
            }
        }
    }

    @PluginMethod
    fun install(call: PluginCall) {
        bridge.execute {
            try {
                if (status().getString("status") != "ready") {
                    throw Exception("安装包尚未下载完成,请重试。")
                }
                verify(JSONObject(preferences.getString("manifest", "{}") ?: "{}"))
                activity.runOnUiThread {
                    try {
                        val permissionRequired = launchInstall()
                        val result = JSObject()
                        result.put("permissionRequired", permissionRequired)
                        call.resolve(result)
                    } catch (error: Exception) {
                        call.reject("无法打开安装界面:${error.message}")
                    }
                }
            } catch (error: Exception) {
                fail(error.message)
                call.reject(error.message)
            }
        }
    }

    private fun launchInstall(): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
            !context.packageManager.canRequestPackageInstalls()
        ) {
            val settings = Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:${context.packageName}"),
            )
            activity.startActivity(settings)
            return true
        }
        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            apkFile(),
        )
        val install = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        activity.startActivity(install)
        return false
    }

    private fun status(): JSObject {
        val saved = preferences.getString("manifest", null)
        val id = preferences.getLong("downloadId", -1)
        if (saved == null) return errorStatus()
        val manifest = JSONObject(saved)
        validate(manifest)
        if (manifest.getLong("versionCode") <= installedCode()) {
            clearDownload()
            preferences.edit().remove("error").commit()
            return errorStatus()
        }
        if (id == -1L) {
            notifyAvailable(manifest)
            val result = JSObject()
            result.put("status", "available")
            result.put("version", manifest.getString("version"))
            result.put("currentVersion", installed().versionName)
            return result
        }
        val result = JSObject()
        result.put("version", manifest.getString("version"))
        result.put("currentVersion", installed().versionName)
        downloads.query(DownloadManager.Query().setFilterById(id)).use { cursor ->
            if (cursor == null || !cursor.moveToFirst()) {
                throw Exception("下载记录已丢失,请重新检查更新。")
            }
            val state = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
            if (state == DownloadManager.STATUS_FAILED) {
                throw Exception("安装包下载失败,请检查网络和存储空间后重试。")
            }
            if (state == DownloadManager.STATUS_SUCCESSFUL) {
                if (verifiedId != id) {
                    verify(manifest)
                    verifiedId = id
                }
                result.put("status", "ready")
                result.put("progress", 100)
            } else {
                val received = cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
                val total = manifest.getLong("size")
                result.put("status", "downloading")
                result.put(
                    "progress",
                    minOf(99.0, maxOf(0.0, received.toDouble() * 100.0 / total.toDouble())),
                )
                result.put(
                    "message",
                    if (state == DownloadManager.STATUS_PAUSED) "下载已暂停,网络恢复后将自动继续。"
                    else "安装包正在自动下载,可继续使用应用。"
                )
            }
        }
        return result
    }

    private fun validate(manifest: JSONObject) {
        UpdatePolicy.validate(
            manifest.getString("version"),
            manifest.getLong("versionCode"),
            manifest.getString("url"),
            manifest.getString("sha256"),
            manifest.getLong("size"),
            BuildConfig.OPENFIC_UPDATE_TEST_BASE_URL
        )
    }

    private fun enqueueDownload(manifest: JSONObject) {
        val version = manifest.getString("version")
        clearDownload()
        val target = apkFile()
        if (!target.parentFile!!.isDirectory && !target.parentFile!!.mkdirs()) {
            throw Exception("Cannot create the update download directory.")
        }
        if (target.exists() && !target.delete()) {
            throw Exception("Cannot remove the previous update package.")
        }
        val request = DownloadManager.Request(Uri.parse(manifest.getString("url")))
            .setTitle("OpenFic $version")
            .setDescription("OpenFic 更新正在下载")
            .setMimeType("application/vnd.android.package-archive")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE)
            .setDestinationInExternalFilesDir(context, null, "updates/update.apk")
            .setAllowedOverMetered(true)
            .setAllowedOverRoaming(false)
        val id = downloads.enqueue(request)
        preferences.edit().putString("manifest", manifest.toString()).putLong("downloadId", id).remove("error").commit()
        verifiedId = -1
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(UPDATE_NOTIFICATION)
        UpdateDownloadNotifications.cancel(context)
    }

    private fun saveAvailable(manifest: JSONObject) {
        preferences.edit().putString("manifest", manifest.toString()).remove("downloadId").remove("error").commit()
        verifiedId = -1
        notifyAvailable(manifest)
    }

    private fun notifyAvailable(manifest: JSONObject) {
        val version = manifest.getString("version")
        if (preferences.getString("notifiedVersion", null) == version) return
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(context, android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (!manager.areNotificationsEnabled()) return
        if (Build.VERSION.SDK_INT >= 26) manager.createNotificationChannel(
            NotificationChannel("app-updates", "应用更新", NotificationManager.IMPORTANCE_DEFAULT)
        )
        val intent = Intent(context, MainActivity::class.java).apply {
            action = "com.openfic.mobile.DOWNLOAD_UPDATE"
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pending = PendingIntent.getActivity(context, UPDATE_NOTIFICATION, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        manager.notify(UPDATE_NOTIFICATION, NotificationCompat.Builder(context, "app-updates")
            .setSmallIcon(R.drawable.openfic_brand)
            .setContentTitle("OpenFic v$version 可用")
            .setContentText("点击下载更新安装包")
            .setContentIntent(pending)
            .setAutoCancel(true)
            .build())
        preferences.edit().putString("notifiedVersion", version).apply()
    }

    @Suppress("DEPRECATION")
    private fun verify(manifest: JSONObject) {
        validate(manifest)
        val file = apkFile()
        if (!UpdatePolicy.matches(file, manifest.getString("sha256"), manifest.getLong("size"))) {
            throw Exception("安装包完整性校验失败,请重新下载。")
        }
        val manager = context.packageManager
        val archive = manager.getPackageArchiveInfo(file.absolutePath, PackageManager.GET_SIGNATURES)
        val local = manager.getPackageInfo(context.packageName, PackageManager.GET_SIGNATURES)
        if (archive == null || local.packageName != archive.packageName ||
            archive.versionCode.toLong() != manifest.getLong("versionCode") ||
            manifest.getString("version") != archive.versionName ||
            archive.versionCode <= installedCode().toInt()) {
            throw Exception("安装包的应用或版本信息不匹配。")
        }
        val archiveSigs = archive.signatures
        val localSigs = local.signatures
        if (archiveSigs == null || localSigs == null ||
            archiveSigs.isEmpty() || !archiveSigs.contentEquals(localSigs)) {
            throw Exception("安装包签名不匹配。测试版不能直接升级到正式版,请安装同一签名渠道的版本。")
        }
    }

    private fun installed(): PackageInfo {
        return context.packageManager.getPackageInfo(context.packageName, 0)
    }

    @Suppress("DEPRECATION")
    private fun installedCode(): Long {
        return installed().versionCode.toLong()
    }

    private fun apkFile(): File {
        val directory = context.getExternalFilesDir(null)
            ?: throw IllegalStateException("应用存储不可用。")
        return File(directory, "updates/update.apk")
    }

    private fun clearDownload() {
        val id = preferences.getLong("downloadId", -1)
        if (id != -1L) downloads.remove(id)
        preferences.edit().remove("downloadId").remove("manifest").commit()
        verifiedId = -1
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(UPDATE_NOTIFICATION)
        UpdateDownloadNotifications.cancel(context)
    }

    private fun fail(message: String?) {
        clearDownload()
        preferences.edit().putString("error", message ?: "更新失败,请重试。").commit()
    }

    private fun errorStatus(): JSObject {
        val result = JSObject()
        val error = preferences.getString("error", null)
        result.put("status", if (error == null) "idle" else "error")
        result.put("message", error ?: "当前没有可用的 Android 更新。")
        try {
            result.put("currentVersion", installed().versionName)
        } catch (ignored: Exception) {
        }
        return result
    }

    private fun fetchJson(address: String): JSONObject? {
        val connection = URL(address).openConnection() as HttpURLConnection
        return try {
            connection.connectTimeout = 15000
            connection.readTimeout = 15000
            connection.setRequestProperty(
                "Accept",
                if (address == LATEST) "application/vnd.github+json" else "application/json"
            )
            connection.setRequestProperty("User-Agent", "OpenFic-Android")
            val code = connection.responseCode
            if (code == 404) return null
            if (code != 200 || !isAllowedUpdateResponse(address, connection.url)) {
                throw Exception("更新服务器返回 $code。")
            }
            connection.inputStream.use { input ->
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                var count: Int
                while (input.read(buffer).also { count = it } != -1) {
                    output.write(buffer, 0, count)
                    if (output.size() > 1048576) {
                        throw Exception("更新信息超过大小限制。")
                    }
                }
                JSONObject(output.toString(StandardCharsets.UTF_8.name()))
            }
        } finally {
            connection.disconnect()
        }
    }

    private fun isAllowedUpdateResponse(address: String, responseUrl: URL): Boolean {
        if (responseUrl.protocol == "https") return true
        val testBaseUrl = BuildConfig.OPENFIC_UPDATE_TEST_BASE_URL
        return testBaseUrl.isNotEmpty() &&
                responseUrl.protocol == "http" &&
                address.startsWith("$testBaseUrl/") &&
                responseUrl.toExternalForm().startsWith("$testBaseUrl/")
    }

    companion object {
        private const val UPDATE_NOTIFICATION = 1001
        private const val RELEASES = "https://github.com/syrizelink/OpenFic/releases/download/"
        private const val LATEST = "https://api.github.com/repos/syrizelink/OpenFic/releases/latest"
    }
}
