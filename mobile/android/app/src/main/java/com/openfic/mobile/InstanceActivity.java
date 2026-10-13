package com.openfic.mobile;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import androidx.activity.OnBackPressedCallback;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;
import org.json.JSONObject;

/**
 * Runs bundled React assets at the selected server's origin. API requests,
 * uploads, streaming and Socket.IO remain ordinary same-origin WebView requests,
 * so HttpOnly / SameSite login cookies work without changing the backend.
 * This WebView has no Capacitor bridge or unrestricted JavaScript interface.
 */
public class InstanceActivity extends AppCompatActivity {
    private WebView webView;
    private String baseUrl;
    private Set<String> assets = new HashSet<>();
    private ValueCallback<Uri[]> fileCallback;
    private byte[] pendingDownload;
    private String pendingDownloadUrl;
    private String pendingDownloadCookie;
    private final ActivityResultLauncher<Intent> filePicker = registerForActivityResult(
        new ActivityResultContracts.StartActivityForResult(), result -> {
            if (fileCallback != null) {
                fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result.getResultCode(), result.getData()));
                fileCallback = null;
            }
        });
    private final ActivityResultLauncher<Intent> savePicker = registerForActivityResult(
        new ActivityResultContracts.StartActivityForResult(), result -> {
            final byte[] bytes = pendingDownload;
            final String downloadUrl = pendingDownloadUrl;
            final String cookie = pendingDownloadCookie;
            pendingDownload = null; pendingDownloadUrl = null; pendingDownloadCookie = null;
            if (result.getResultCode() != Activity.RESULT_OK || result.getData() == null || (bytes == null && downloadUrl == null)) return;
            Uri uri = result.getData().getData();
            if (uri == null) return;
            new Thread(() -> {
                try (java.io.OutputStream output = getContentResolver().openOutputStream(uri)) {
                    if (output == null) throw new java.io.IOException("无法打开文件");
                    if (bytes != null) output.write(bytes);
                    else {
                        java.net.HttpURLConnection connection = (java.net.HttpURLConnection) new java.net.URL(downloadUrl).openConnection();
                        connection.setConnectTimeout(15000); connection.setReadTimeout(120000);
                        connection.setInstanceFollowRedirects(false);
                        if (cookie != null) connection.setRequestProperty("Cookie", cookie);
                        try {
                            if (connection.getResponseCode() != 200) throw new java.io.IOException("下载失败");
                            try (InputStream stream = connection.getInputStream()) {
                                byte[] buffer = new byte[8192]; int count;
                                while ((count = stream.read(buffer)) != -1) output.write(buffer, 0, count);
                            }
                        } finally { connection.disconnect(); }
                    }
                    runOnUiThread(() -> Toast.makeText(this, "文件已保存", Toast.LENGTH_SHORT).show());
                } catch (Exception error) { runOnUiThread(() -> Toast.makeText(this, "保存失败", Toast.LENGTH_LONG).show()); }
            }).start();
        });

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        try {
            baseUrl = InstanceUrl.normalize(getIntent().getStringExtra("url"));
            listAssets("public/frontend", "");
        } catch (Exception error) { finish(); return; }
        boolean dark = (getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
        int background = dark ? Color.rgb(24, 24, 27) : Color.rgb(250, 250, 250);
        int foreground = dark ? Color.WHITE : Color.rgb(24, 24, 27);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(background);
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(android.view.Gravity.CENTER_VERTICAL);
        Button instances = new Button(this);
        instances.setText("‹ 实例");
        instances.setContentDescription("返回远程实例列表");
        instances.setTextColor(foreground); instances.setBackgroundColor(Color.TRANSPARENT);
        instances.setOnClickListener(view -> finish());
        toolbar.addView(instances, new LinearLayout.LayoutParams(dp(82), dp(48)));
        TextView title = new TextView(this);
        title.setText(getIntent().getStringExtra("name")); title.setTextColor(foreground);
        title.setSingleLine(true); title.setEllipsize(android.text.TextUtils.TruncateAt.END);
        toolbar.addView(title, new LinearLayout.LayoutParams(0, dp(48), 1));
        title.setGravity(android.view.Gravity.CENTER_VERTICAL);
        Button reload = new Button(this);
        reload.setText("↻"); reload.setTextSize(24); reload.setTextColor(foreground);
        reload.setContentDescription("重新加载实例"); reload.setBackgroundColor(Color.TRANSPARENT);
        reload.setOnClickListener(view -> webView.reload());
        toolbar.addView(reload, new LinearLayout.LayoutParams(dp(54), dp(48)));
        layout.addView(toolbar);
        webView = new WebView(this);
        webView.setBackgroundColor(background);
        layout.addView(webView, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(layout);
        ViewCompat.setOnApplyWindowInsetsListener(layout, (view, insets) -> {
            androidx.core.graphics.Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.ime());
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return WindowInsetsCompat.CONSUMED;
        });
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false); settings.setAllowContentAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(true);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);
        webView.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (!sameOrigin(uri) || !request.getMethod().equals("GET")) return null;
                String path = uri.getPath();
                if ("/runtime-config.json".equals(path)) {
                    try {
                        String json = new JSONObject().put("backendBaseUrl", baseUrl).toString();
                        return response("application/json", new ByteArrayInputStream(json.getBytes(StandardCharsets.UTF_8)));
                    } catch (Exception error) { return null; }
                }
                // Never replace API/media/download responses with index.html.
                if (isBackendPath(path)) return null;
                if ("/sw.js".equals(path)) return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
                String asset = path == null ? "" : path.replaceFirst("^/", "");
                if (asset.isEmpty() || request.isForMainFrame()) asset = "index.html";
                if (!assets.contains(asset)) return null;
                try { return response(mime(asset), getAssets().open("public/frontend/" + asset)); }
                catch (Exception error) { return null; }
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (sameOrigin(uri)) return false;
                if (request.isForMainFrame()) openExternal(uri);
                return true;
            }
            @Override public void onPageFinished(WebView view, String url) {
                CookieManager.getInstance().flush();
                view.evaluateJavascript(BLOB_DOWNLOAD_SCRIPT, null);
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try { filePicker.launch(params.createIntent()); }
                catch (ActivityNotFoundException error) { fileCallback.onReceiveValue(null); fileCallback = null; }
                return true;
            }
        });
        // Origin-scoped message channel only allows a user-confirmed document save.
        if (androidx.webkit.WebViewFeature.isFeatureSupported(androidx.webkit.WebViewFeature.WEB_MESSAGE_LISTENER)) {
            androidx.webkit.WebViewCompat.addWebMessageListener(webView, "OpenFicDownloads", Collections.singleton(baseUrl), (view, message, origin, mainFrame, reply) -> {
                if (!mainFrame || pendingDownload != null || pendingDownloadUrl != null) return;
                try {
                    JSONObject data = new JSONObject(message.getData());
                    String encoded = data.getString("base64");
                    if (encoded.length() > 70_000_000) throw new Exception("文件过大");
                    pendingDownload = android.util.Base64.decode(encoded, android.util.Base64.DEFAULT);
                    String filename = data.optString("filename", "OpenFic-export.txt").replaceAll("[/\\\\\\p{Cntrl}]", "_");
                    Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType("application/octet-stream"); intent.putExtra(Intent.EXTRA_TITLE, filename);
                    savePicker.launch(intent);
                } catch (Exception error) { pendingDownload = null; Toast.makeText(this, "无法保存此文件", Toast.LENGTH_LONG).show(); }
            });
        }
        webView.setDownloadListener((url, userAgent, disposition, mime, length) -> {
            Uri uri = Uri.parse(url);
            if (!sameOrigin(uri)) { openExternal(uri); return; }
            try {
                if (pendingDownload != null || pendingDownloadUrl != null) return;
                pendingDownloadUrl = url;
                pendingDownloadCookie = CookieManager.getInstance().getCookie(url);
                Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType(mime == null || mime.isEmpty() ? "application/octet-stream" : mime);
                intent.putExtra(Intent.EXTRA_TITLE, android.webkit.URLUtil.guessFileName(url, disposition, mime));
                savePicker.launch(intent);
            } catch (Exception error) { pendingDownloadUrl = null; pendingDownloadCookie = null; Toast.makeText(this, "无法保存此文件", Toast.LENGTH_LONG).show(); }
        });
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack(); else finish();
            }
        });
        if (state != null) webView.restoreState(state); else webView.loadUrl(baseUrl + "/");
    }
    private int dp(int value) { return (int) (value * getResources().getDisplayMetrics().density); }
    private boolean sameOrigin(Uri uri) {
        Uri base = Uri.parse(baseUrl);
        return base.getScheme().equals(uri.getScheme()) && base.getHost().equalsIgnoreCase(uri.getHost() == null ? "" : uri.getHost()) && base.getPort() == uri.getPort();
    }
    private boolean isBackendPath(String path) {
        if (path == null) return false;
        for (String prefix : new String[]{"/api", "/socket.io", "/covers", "/character-images", "/agent-attachments", "/icons"}) {
            if (path.equals(prefix) || path.startsWith(prefix + "/")) return true;
        }
        return false;
    }
    private void listAssets(String root, String relative) throws java.io.IOException {
        String[] children = getAssets().list(root + (relative.isEmpty() ? "" : "/" + relative));
        if (children == null || children.length == 0) { assets.add(relative); return; }
        for (String child : children) listAssets(root, relative.isEmpty() ? child : relative + "/" + child);
    }
    private WebResourceResponse response(String mime, InputStream stream) {
        return new WebResourceResponse(mime, "UTF-8", 200, "OK", Collections.singletonMap("Cache-Control", "no-store"), stream);
    }
    private String mime(String path) {
        if (path.endsWith(".js") || path.endsWith(".mjs")) return "application/javascript";
        if (path.endsWith(".css")) return "text/css";
        if (path.endsWith(".svg")) return "image/svg+xml";
        if (path.endsWith(".woff2")) return "font/woff2";
        if (path.endsWith(".woff")) return "font/woff";
        if (path.endsWith(".webmanifest") || path.endsWith(".json")) return "application/json";
        if (path.endsWith(".png")) return "image/png";
        if (path.endsWith(".html")) return "text/html";
        return "application/octet-stream";
    }
    private void openExternal(Uri uri) {
        if (!("https".equals(uri.getScheme()) || "http".equals(uri.getScheme()) || "mailto".equals(uri.getScheme()))) return;
        try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
        catch (ActivityNotFoundException error) { Toast.makeText(this, "无法打开此链接", Toast.LENGTH_SHORT).show(); }
    }
    @Override protected void onSaveInstanceState(Bundle state) { if (webView != null) webView.saveState(state); super.onSaveInstanceState(state); }
    @Override protected void onPause() { if (webView != null) webView.onPause(); CookieManager.getInstance().flush(); super.onPause(); }
    @Override protected void onResume() { super.onResume(); if (webView != null) webView.onResume(); }
    @Override protected void onDestroy() {
        if (fileCallback != null) fileCallback.onReceiveValue(null);
        if (webView != null) { webView.stopLoading(); webView.destroy(); }
        super.onDestroy();
    }
    private static final String BLOB_DOWNLOAD_SCRIPT = "(function(){if(window.__openficBlobDownloads)return;window.__openficBlobDownloads=true;const blobs=new Map();const create=URL.createObjectURL.bind(URL);const revoke=URL.revokeObjectURL.bind(URL);URL.createObjectURL=(blob)=>{const url=create(blob);blobs.set(url,blob);return url;};URL.revokeObjectURL=(url)=>{blobs.delete(url);revoke(url);};document.addEventListener('click',function(event){const a=event.target.closest&&event.target.closest('a');if(!a||!a.href.startsWith('blob:')||!window.OpenFicDownloads)return;const blob=blobs.get(a.href);if(!blob)return;event.preventDefault();const reader=new FileReader();reader.onload=()=>OpenFicDownloads.postMessage(JSON.stringify({filename:a.download||'OpenFic-export.txt',base64:reader.result.split(',')[1]}));reader.readAsDataURL(blob);},true);})();";
}
