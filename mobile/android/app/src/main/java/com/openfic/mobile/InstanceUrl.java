package com.openfic.mobile;

import java.net.URI;
import java.util.Locale;

/** Validate at the native boundary as well as in the connection form. */
public final class InstanceUrl {
    private InstanceUrl() {}
    public static String normalize(String input) {
        URI uri = URI.create(input.trim());
        String scheme = uri.getScheme();
        String host = uri.getHost();
        if (!("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) || host == null
                || uri.getUserInfo() != null || uri.getQuery() != null || uri.getFragment() != null
                || (uri.getPath() != null && !uri.getPath().isEmpty() && !"/".equals(uri.getPath()))) {
            throw new IllegalArgumentException("请填写完整的 HTTP/HTTPS 实例根地址。");
        }
        host = host.toLowerCase(Locale.ROOT);
        if (host.equals("localhost") || host.endsWith(".localhost") || host.equals("[::1]")
                || host.equals("::1") || host.equals("0.0.0.0") || host.startsWith("127.")) {
            throw new IllegalArgumentException("请使用远程服务器或局域网地址，不能连接手机本机。");
        }
        int port = uri.getPort();
        if (port > 65535 || port == 0) throw new IllegalArgumentException("服务器端口无效。");
        String normalizedScheme = scheme.toLowerCase(Locale.ROOT);
        boolean defaultPort = port == -1 || (port == 443 && normalizedScheme.equals("https")) || (port == 80 && normalizedScheme.equals("http"));
        return normalizedScheme + "://" + host + (defaultPort ? "" : ":" + port);
    }
}
