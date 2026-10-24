package com.openfic.mobile

import java.net.HttpURLConnection
import java.net.URI
import java.util.Locale

/** Validate at the native boundary as well as in the connection form. */
object InstanceUrl {
    private val ngrokDomains = listOf(
        "ngrok.app", "ngrok.dev", "ngrok.pizza",
        "ngrok-free.app", "ngrok-free.dev", "ngrok.io",
    )

    fun isNgrok(input: String): Boolean {
        val uri = try {
            URI.create(input)
        } catch (_: IllegalArgumentException) {
            return false
        }
        if (!(uri.scheme.equals("https", ignoreCase = true) ||
                uri.scheme.equals("http", ignoreCase = true)) || uri.userInfo != null) return false
        val host = uri.host?.lowercase(Locale.ROOT) ?: return false
        return ngrokDomains.any { host == it || host.endsWith(".$it") }
    }

    fun applyNgrokHeaders(connection: HttpURLConnection) {
        if (isNgrok(connection.url.toString())) {
            connection.setRequestProperty("ngrok-skip-browser-warning", "1")
        }
    }

    fun webViewUserAgent(input: String, defaultUserAgent: String): String {
        if (!isNgrok(input)) return defaultUserAgent
        // Preserve Android detection used by the editor's input-method handling.
        val platform = Regex("Android [0-9.]+").find(defaultUserAgent)?.value ?: "Android"
        return "OpenFic-Android/${BuildConfig.VERSION_NAME} ($platform)"
    }

    @JvmStatic
    fun normalize(input: String): String {
        val uri = URI.create(input.trim())
        val scheme = uri.scheme
        val host = uri.host
        
        if (!(scheme.equals("http", ignoreCase = true) || scheme.equals("https", ignoreCase = true)) || 
            host == null || uri.userInfo != null || uri.query != null || uri.fragment != null ||
            (uri.path != null && uri.path.isNotEmpty() && uri.path != "/")) {
            throw IllegalArgumentException("请填写完整的 HTTP/HTTPS 实例根地址。")
        }
        
        val normalizedHost = host.lowercase(Locale.ROOT)
        if (normalizedHost == "localhost" || normalizedHost.endsWith(".localhost") || 
            normalizedHost == "[::1]" || normalizedHost == "::1" || 
            normalizedHost == "0.0.0.0" || normalizedHost.startsWith("127.")) {
            throw IllegalArgumentException("请使用远程服务器或局域网地址,不能连接手机本机。")
        }
        
        val port = uri.port
        if (port > 65535 || port == 0) {
            throw IllegalArgumentException("服务器端口无效。")
        }
        
        val normalizedScheme = scheme.lowercase(Locale.ROOT)
        val defaultPort = port == -1 || 
            (port == 443 && normalizedScheme == "https") || 
            (port == 80 && normalizedScheme == "http")
        
        return "$normalizedScheme://$normalizedHost${if (defaultPort) "" else ":$port"}"
    }
}
