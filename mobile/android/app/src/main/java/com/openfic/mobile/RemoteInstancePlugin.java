package com.openfic.mobile;

import android.content.Intent;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import org.json.JSONObject;

@CapacitorPlugin(name = "RemoteInstance")
public class RemoteInstancePlugin extends Plugin {
    @PluginMethod
    public void check(PluginCall call) {
        final String baseUrl;
        try { baseUrl = InstanceUrl.normalize(call.getString("url", "")); }
        catch (Exception error) { call.reject(error.getMessage()); return; }
        getBridge().execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(baseUrl + "/api/v1/health").openConnection();
                connection.setConnectTimeout(10000);
                connection.setReadTimeout(10000);
                connection.setInstanceFollowRedirects(false);
                connection.setRequestProperty("Accept", "application/json");
                int status = connection.getResponseCode();
                if (status != 200) throw new Exception("服务器返回 " + status + "，请检查实例根地址。");
                ByteArrayOutputStream output = new ByteArrayOutputStream();
                try (InputStream stream = connection.getInputStream()) {
                    byte[] buffer = new byte[2048];
                    int count;
                    while ((count = stream.read(buffer)) != -1) {
                        output.write(buffer, 0, count);
                        if (output.size() > 65536) throw new Exception("服务器响应不是有效的健康检查。");
                    }
                }
                JSONObject data = new JSONObject(output.toString(StandardCharsets.UTF_8.name()));
                String health = data.optString("status");
                if (!(health.equals("healthy") || health.equals("ok")) || data.optString("version").isEmpty()) {
                    throw new Exception("该地址不是可用的 OpenFic 实例。");
                }
                JSObject result = new JSObject();
                result.put("version", data.getString("version"));
                call.resolve(result);
            } catch (javax.net.ssl.SSLException error) {
                call.reject("证书验证失败，请使用具有有效证书的 HTTPS 地址。");
            } catch (java.net.SocketTimeoutException error) {
                call.reject("连接超时，请检查网络和服务器地址。");
            } catch (Exception error) {
                call.reject("无法连接实例：" + error.getMessage());
            } finally { if (connection != null) connection.disconnect(); }
        });
    }

    @PluginMethod
    public void open(PluginCall call) {
        try {
            String url = InstanceUrl.normalize(call.getString("url", ""));
            Intent intent = new Intent(getActivity(), InstanceActivity.class);
            intent.putExtra("url", url);
            intent.putExtra("name", call.getString("name", "OpenFic"));
            getActivity().runOnUiThread(() -> { getActivity().startActivity(intent); call.resolve(); });
        } catch (Exception error) { call.reject(error.getMessage()); }
    }
}
