package com.openfic.mobile

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.res.Configuration
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.webkit.*
import android.widget.LinearLayout
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets

/**
 * Runs bundled React assets at the selected server's origin. API requests,
 * uploads, streaming and Socket.IO remain ordinary same-origin WebView requests,
 * so HttpOnly / SameSite login cookies work without changing the backend.
 * This WebView has no Capacitor bridge or unrestricted JavaScript interface.
 */
class InstanceActivity : AppCompatActivity() {
    private lateinit var webView: WebView
    private lateinit var baseUrl: String
    private val assetPaths = mutableSetOf<String>()
    private var fileCallback: ValueCallback<Array<Uri>>? = null
    private var pendingDownload: ByteArray? = null
    private var pendingDownloadUrl: String? = null
    private var pendingDownloadCookie: String? = null

    private val filePicker: ActivityResultLauncher<Intent> = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        fileCallback?.onReceiveValue(
            WebChromeClient.FileChooserParams.parseResult(result.resultCode, result.data)
        )
        fileCallback = null
    }

    private val savePicker: ActivityResultLauncher<Intent> = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val bytes = pendingDownload
        val downloadUrl = pendingDownloadUrl
        val cookie = pendingDownloadCookie
        pendingDownload = null
        pendingDownloadUrl = null
        pendingDownloadCookie = null

        if (result.resultCode != Activity.RESULT_OK || result.data == null || 
            (bytes == null && downloadUrl == null)) return@registerForActivityResult

        val uri = result.data?.data ?: return@registerForActivityResult

        Thread {
            try {
                contentResolver.openOutputStream(uri)?.use { output ->
                    if (bytes != null) {
                        output.write(bytes)
                    } else if (downloadUrl != null) {
                        val connection = URL(downloadUrl).openConnection() as HttpURLConnection
                        connection.connectTimeout = 15000
                        connection.readTimeout = 120000
                        connection.instanceFollowRedirects = false
                        if (cookie != null) {
                            connection.setRequestProperty("Cookie", cookie)
                        }
                        try {
                            if (connection.responseCode != 200) {
                                throw IOException("下载失败")
                            }
                            connection.inputStream.use { stream ->
                                val buffer = ByteArray(8192)
                                var count: Int
                                while (stream.read(buffer).also { count = it } != -1) {
                                    output.write(buffer, 0, count)
                                }
                            }
                        } finally {
                            connection.disconnect()
                        }
                    }
                    runOnUiThread {
                        showNotice("文件已保存")
                    }
                } ?: throw IOException("无法打开文件")
            } catch (error: Exception) {
                runOnUiThread {
                    showNotice("保存失败", true)
                }
            }
        }.start()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        try {
            baseUrl = InstanceUrl.normalize(intent.getStringExtra("url") ?: "")
            listAssets("public/frontend", "")
        } catch (error: Exception) {
            finish()
            return
        }

        val dark = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == 
                   Configuration.UI_MODE_NIGHT_YES
        val background = if (dark) Color.rgb(24, 24, 27) else Color.rgb(250, 250, 250)

        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(background)
        }

        webView = WebView(this).apply {
            setBackgroundColor(background)
        }
        layout.addView(webView, LinearLayout.LayoutParams(-1, 0, 1f))

        setContentView(layout)
        androidx.core.view.WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = Color.TRANSPARENT
        window.navigationBarColor = Color.TRANSPARENT
        if (android.os.Build.VERSION.SDK_INT >= 29) {
            window.isNavigationBarContrastEnforced = false
            window.isStatusBarContrastEnforced = false
        }
        ViewCompat.setOnApplyWindowInsetsListener(layout) { view, insets ->
            val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
            view.setPadding(0, 0, 0, ime.bottom)
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            val density = resources.displayMetrics.density
            safeAreaScript = "document.documentElement.style.setProperty('--mobile-safe-top','${bars.top / density}px');document.documentElement.style.setProperty('--mobile-safe-bottom','${if (ime.bottom > 0) 0f else bars.bottom / density}px');document.documentElement.style.setProperty('--mobile-safe-left','${bars.left / density}px');document.documentElement.style.setProperty('--mobile-safe-right','${bars.right / density}px');"
            webView.evaluateJavascript(safeAreaScript, null)
            WindowInsetsCompat.CONSUMED
        }

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = true
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            mediaPlaybackRequiresUserGesture = true
        }

        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setAcceptThirdPartyCookies(webView, false)
        }

        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView,
                request: WebResourceRequest
            ): WebResourceResponse? {
                val uri = request.url
                if (!sameOrigin(uri) || request.method != "GET") return null

                val path = uri.path
                if (path == "/runtime-config.json") {
                    return try {
                        val json = JSONObject().put("backendBaseUrl", baseUrl).toString()
                        response(
                            "application/json",
                            ByteArrayInputStream(json.toByteArray(StandardCharsets.UTF_8))
                        )
                    } catch (error: Exception) {
                        null
                    }
                }

                if (isBackendPath(path)) return null

                if (path == "/sw.js") {
                    return WebResourceResponse(
                        "text/plain", "UTF-8", 404, "Not Found",
                        emptyMap(), ByteArrayInputStream(ByteArray(0))
                    )
                }

                var asset = path?.replaceFirst(Regex("^/"), "") ?: ""
                if (asset.isEmpty() || request.isForMainFrame) asset = "index.html"
                if (!assetPaths.contains(asset)) return null

                return try {
                    response(mime(asset), applicationContext.assets.open("public/frontend/$asset"))
                } catch (error: Exception) {
                    null
                }
            }

            override fun shouldOverrideUrlLoading(
                view: WebView,
                request: WebResourceRequest
            ): Boolean {
                val uri = request.url
                if (sameOrigin(uri)) return false
                if (request.isForMainFrame) openExternal(uri)
                return true
            }

            override fun onPageFinished(view: WebView, url: String) {
                CookieManager.getInstance().flush()
                view.evaluateJavascript(safeAreaScript, null)
                view.evaluateJavascript(BLOB_DOWNLOAD_SCRIPT, null)
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                webView: WebView,
                filePathCallback: ValueCallback<Array<Uri>>,
                fileChooserParams: FileChooserParams
            ): Boolean {
                fileCallback?.onReceiveValue(null)
                fileCallback = filePathCallback
                return try {
                    filePicker.launch(fileChooserParams.createIntent())
                    true
                } catch (error: ActivityNotFoundException) {
                    fileCallback?.onReceiveValue(null)
                    fileCallback = null
                    false
                }
            }
        }

        if (androidx.webkit.WebViewFeature.isFeatureSupported(androidx.webkit.WebViewFeature.WEB_MESSAGE_LISTENER)) {
            androidx.webkit.WebViewCompat.addWebMessageListener(webView, "OpenFicAppearance", setOf(baseUrl)) { _, message, _, isMainFrame, _ ->
                if (isMainFrame) {
                    try {
                        val data = JSONObject(message.data ?: "{}")
                        val light = data.optString("appearance") == "light"
                        val controller = androidx.core.view.WindowCompat.getInsetsController(window, webView)
                        controller.isAppearanceLightStatusBars = light
                        controller.isAppearanceLightNavigationBars = light
                        val color = Color.parseColor(data.getString("background"))
                        webView.setBackgroundColor(color)
                        layout.setBackgroundColor(color)
                    } catch (_: Exception) { }
                }
            }
            androidx.webkit.WebViewCompat.addWebMessageListener(
                webView,
                "OpenFicDownloads",
                setOf(baseUrl)
            ) { _, message, _, isMainFrame, _ ->
                if (!isMainFrame || pendingDownload != null || pendingDownloadUrl != null) return@addWebMessageListener
                try {
                    val data = JSONObject(message.data)
                    val encoded = data.getString("base64")
                    if (encoded.length > 70_000_000) throw Exception("文件过大")
                    pendingDownload = android.util.Base64.decode(encoded, android.util.Base64.DEFAULT)
                    val filename = data.optString("filename", "OpenFic-export.txt")
                        .replace(Regex("[/\\\\\\p{Cntrl}]"), "_")
                    val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                        addCategory(Intent.CATEGORY_OPENABLE)
                        type = "application/octet-stream"
                        putExtra(Intent.EXTRA_TITLE, filename)
                    }
                    savePicker.launch(intent)
                } catch (error: Exception) {
                    pendingDownload = null
                    showNotice("无法保存此文件", true)
                }
            }
        }

        webView.setDownloadListener { url, _, disposition, mimeType, _ ->
            val uri = Uri.parse(url)
            if (!sameOrigin(uri)) {
                openExternal(uri)
                return@setDownloadListener
            }
            try {
                if (pendingDownload != null || pendingDownloadUrl != null) return@setDownloadListener
                pendingDownloadUrl = url
                pendingDownloadCookie = CookieManager.getInstance().getCookie(url)
                val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = if (mimeType.isNullOrEmpty()) "application/octet-stream" else mimeType
                    putExtra(Intent.EXTRA_TITLE, URLUtil.guessFileName(url, disposition, mimeType))
                }
                savePicker.launch(intent)
            } catch (error: Exception) {
                pendingDownloadUrl = null
                pendingDownloadCookie = null
                showNotice("无法保存此文件", true)
            }
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })

        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState)
        } else {
            webView.loadUrl("$baseUrl/")
        }
        ViewCompat.requestApplyInsets(layout)
    }

    private var safeAreaScript = ""

    private fun showNotice(message: String, error: Boolean = false) {
        if (isDestroyed || !::webView.isInitialized) return
        val detail = JSONObject().put("message", message).put("error", error)
        webView.evaluateJavascript(
            "window.dispatchEvent(new CustomEvent('openfic:native-notice',{detail:$detail}));",
            null,
        )
    }

    private fun sameOrigin(uri: Uri): Boolean {
        val base = Uri.parse(baseUrl)
        return base.scheme == uri.scheme &&
                base.host.equals(uri.host ?: "", ignoreCase = true) &&
                base.port == uri.port
    }

    private fun isBackendPath(path: String?): Boolean {
        if (path == null) return false
        val prefixes = arrayOf("/api", "/socket.io", "/covers", "/character-images", 
                               "/agent-attachments", "/icons")
        return prefixes.any { prefix ->
            path == prefix || path.startsWith("$prefix/")
        }
    }

    private fun listAssets(root: String, relative: String) {
        val children = applicationContext.assets.list("$root${if (relative.isEmpty()) "" else "/$relative"}")
        if (children == null || children.isEmpty()) {
            assetPaths.add(relative)
            return
        }
        for (child in children) {
            listAssets(root, if (relative.isEmpty()) child else "$relative/$child")
        }
    }

    private fun response(mimeType: String, stream: InputStream): WebResourceResponse {
        return WebResourceResponse(
            mimeType, "UTF-8", 200, "OK",
            mapOf("Cache-Control" to "no-store"), stream
        )
    }

    private fun mime(path: String): String {
        return when {
            path.endsWith(".js") || path.endsWith(".mjs") -> "application/javascript"
            path.endsWith(".css") -> "text/css"
            path.endsWith(".svg") -> "image/svg+xml"
            path.endsWith(".woff2") -> "font/woff2"
            path.endsWith(".woff") -> "font/woff"
            path.endsWith(".webmanifest") || path.endsWith(".json") -> "application/json"
            path.endsWith(".png") -> "image/png"
            path.endsWith(".html") -> "text/html"
            else -> "application/octet-stream"
        }
    }

    private fun openExternal(uri: Uri) {
        if (!(uri.scheme == "https" || uri.scheme == "http" || uri.scheme == "mailto")) return
        try {
            startActivity(Intent(Intent.ACTION_VIEW, uri))
        } catch (error: ActivityNotFoundException) {
            showNotice("无法打开此链接", true)
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        webView.saveState(outState)
        super.onSaveInstanceState(outState)
    }

    override fun onPause() {
        webView.onPause()
        CookieManager.getInstance().flush()
        super.onPause()
    }

    override fun onResume() {
        super.onResume()
        webView.onResume()
    }

    override fun onDestroy() {
        fileCallback?.onReceiveValue(null)
        webView.stopLoading()
        webView.destroy()
        super.onDestroy()
    }

    companion object {
        private const val BLOB_DOWNLOAD_SCRIPT = """(function(){if(window.__openficBlobDownloads)return;window.__openficBlobDownloads=true;const blobs=new Map();const create=URL.createObjectURL.bind(URL);const revoke=URL.revokeObjectURL.bind(URL);URL.createObjectURL=(blob)=>{const url=create(blob);blobs.set(url,blob);return url;};URL.revokeObjectURL=(url)=>{blobs.delete(url);revoke(url);};document.addEventListener('click',function(event){const a=event.target.closest&&event.target.closest('a');if(!a||!a.href.startsWith('blob:')||!window.OpenFicDownloads)return;const blob=blobs.get(a.href);if(!blob)return;event.preventDefault();const reader=new FileReader();reader.onload=()=>OpenFicDownloads.postMessage(JSON.stringify({filename:a.download||'OpenFic-export.txt',base64:reader.result.split(',')[1]}));reader.readAsDataURL(blob);},true);})();"""
    }
}
