package com.openfic.mobile

import java.net.URI
import java.util.Locale

/** Validate at the native boundary as well as in the connection form. */
object InstanceUrl {
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
