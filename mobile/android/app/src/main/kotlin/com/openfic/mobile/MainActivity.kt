package com.openfic.mobile

import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.view.View
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.getcapacitor.BridgeActivity

class MainActivity : BridgeActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        registerPlugin(RemoteInstancePlugin::class.java)
        registerPlugin(AppUpdatePlugin::class.java)
        super.onCreate(savedInstanceState)

        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = Color.TRANSPARENT
        window.navigationBarColor = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Color.TRANSPARENT
        } else {
            LEGACY_NAVIGATION_BACKGROUND
        }
        window.decorView.setBackgroundColor(SHELL_BACKGROUND)
        
        val barsController = WindowCompat.getInsetsController(window, window.decorView)
        barsController.isAppearanceLightStatusBars = true
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            barsController.isAppearanceLightNavigationBars = true
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            window.isStatusBarContrastEnforced = false
            window.isNavigationBarContrastEnforced = false
        }

        // Keep web content clear of the status bar, navigation bar and keyboard.
        val content = findViewById<View>(android.R.id.content)
        ViewCompat.setOnApplyWindowInsetsListener(content) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        ViewCompat.requestApplyInsets(content)
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            val preferences = getSharedPreferences("openfic.updates", MODE_PRIVATE)
            if (!preferences.getBoolean("notificationPermissionRequested", false)) {
                preferences.edit().putBoolean("notificationPermissionRequested", true).apply()
                requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 1001)
            }
        }
    }

    companion object {
        private val SHELL_BACKGROUND = Color.rgb(252, 252, 252)
        private val LEGACY_NAVIGATION_BACKGROUND = Color.rgb(24, 24, 27)
    }
}
