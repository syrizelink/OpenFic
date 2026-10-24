package com.openfic.mobile

import android.content.Intent
import androidx.activity.result.ActivityResult
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import com.getcapacitor.annotation.ActivityCallback
import com.google.zxing.client.android.Intents
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets
import javax.net.ssl.SSLException
import java.net.SocketTimeoutException

@CapacitorPlugin(name = "RemoteInstance")
class RemoteInstancePlugin : Plugin() {
    @PluginMethod
    fun scanUrl(call: PluginCall) {
        activity.runOnUiThread {
            try {
                val options = ScanOptions()
                    .setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                    .setPrompt("扫描远程隧道二维码")
                    .setBeepEnabled(false)
                    .setOrientationLocked(false)
                startActivityForResult(call, options.createScanIntent(activity), "scanUrlResult")
            } catch (error: Exception) {
                call.reject("无法启动扫码，请检查相机是否可用。", error)
            }
        }
    }

    @ActivityCallback
    private fun scanUrlResult(call: PluginCall?, result: ActivityResult) {
        if (call == null) return
        if (result.data?.getBooleanExtra(Intents.Scan.MISSING_CAMERA_PERMISSION, false) == true) {
            call.reject("请允许使用相机后重试扫描二维码。")
            return
        }
        val scan = ScanContract().parseResult(result.resultCode, result.data)
        call.resolve(JSObject().apply { put("value", scan.contents ?: JSONObject.NULL) })
    }

    @PluginMethod
    fun check(call: PluginCall) {
        val baseUrl: String = try {
            InstanceUrl.normalize(call.getString("url") ?: "")
        } catch (error: Exception) {
            call.reject(error.message)
            return
        }
        
        bridge.execute {
            var connection: HttpURLConnection? = null
            try {
                connection = URL("$baseUrl/api/v1/health").openConnection() as HttpURLConnection
                connection.connectTimeout = 10000
                connection.readTimeout = 10000
                connection.instanceFollowRedirects = false
                connection.setRequestProperty("Accept", "application/json")
                InstanceUrl.applyNgrokHeaders(connection)
                
                val status = connection.responseCode
                if (status != 200) {
                    throw Exception("服务器返回 $status,请检查实例根地址。")
                }
                
                val output = ByteArrayOutputStream()
                connection.inputStream.use { stream ->
                    val buffer = ByteArray(2048)
                    var count: Int
                    while (stream.read(buffer).also { count = it } != -1) {
                        output.write(buffer, 0, count)
                        if (output.size() > 65536) {
                            throw Exception("服务器响应不是有效的健康检查。")
                        }
                    }
                }
                
                val data = JSONObject(output.toString(StandardCharsets.UTF_8.name()))
                val health = data.optString("status")
                if (!(health == "healthy" || health == "ok") || data.optString("version").isEmpty()) {
                    throw Exception("该地址不是可用的 OpenFic 实例。")
                }
                
                val result = JSObject()
                result.put("version", data.getString("version"))
                call.resolve(result)
            } catch (error: SSLException) {
                call.reject("证书验证失败,请使用具有有效证书的 HTTPS 地址。")
            } catch (error: SocketTimeoutException) {
                call.reject("连接超时,请检查网络和服务器地址。")
            } catch (error: Exception) {
                call.reject("无法连接实例:${error.message}")
            } finally {
                connection?.disconnect()
            }
        }
    }

    @PluginMethod
    fun open(call: PluginCall) {
        try {
            val url = InstanceUrl.normalize(call.getString("url") ?: "")
            val intent = Intent(activity, InstanceActivity::class.java).apply {
                putExtra("url", url)
                putExtra("name", call.getString("name") ?: "OpenFic")
            }
            activity.runOnUiThread {
                activity.startActivity(intent)
                call.resolve()
            }
        } catch (error: Exception) {
            call.reject(error.message)
        }
    }
}
