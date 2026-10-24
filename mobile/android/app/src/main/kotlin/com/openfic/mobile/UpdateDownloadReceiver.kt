package com.openfic.mobile

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.app.DownloadManager
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import org.json.JSONObject

class UpdateDownloadReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != DownloadManager.ACTION_DOWNLOAD_COMPLETE) return
        val downloadId = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1)
        val preferences = context.getSharedPreferences("openfic.updates", Context.MODE_PRIVATE)
        if (downloadId == -1L || preferences.getLong("downloadId", -1) != downloadId) return

        val downloads = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        downloads.query(DownloadManager.Query().setFilterById(downloadId)).use { cursor ->
            if (cursor == null || !cursor.moveToFirst()) return
            if (cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)) !=
                DownloadManager.STATUS_SUCCESSFUL
            ) return
        }

        val version = JSONObject(preferences.getString("manifest", "{}") ?: "{}")
            .optString("version", "新版本")
        UpdateDownloadNotifications.showReady(context, version)
    }
}

internal object UpdateDownloadNotifications {
    private const val CHANNEL_ID = "app-updates"
    private const val READY_NOTIFICATION = 1002

    fun cancel(context: Context) {
        context.getSystemService(NotificationManager::class.java).cancel(READY_NOTIFICATION)
    }

    fun showReady(context: Context, version: String) {
        if (android.os.Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, android.Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) return
        val manager = context.getSystemService(NotificationManager::class.java)
        if (!manager.areNotificationsEnabled()) return
        if (android.os.Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "应用更新", NotificationManager.IMPORTANCE_DEFAULT),
            )
        }
        val openIntent = Intent(context, MainActivity::class.java).apply {
            action = "com.openfic.mobile.INSTALL_UPDATE"
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            READY_NOTIFICATION,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        manager.notify(
            READY_NOTIFICATION,
            NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(R.drawable.openfic_brand)
                .setContentTitle("OpenFic v$version 下载完成")
                .setContentText("点击安装更新")
                .setContentIntent(pendingIntent)
                .setAutoCancel(true)
                .setOnlyAlertOnce(true)
                .build(),
        )
    }
}
