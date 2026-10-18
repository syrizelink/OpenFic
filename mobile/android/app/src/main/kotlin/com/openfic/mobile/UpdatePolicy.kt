package com.openfic.mobile

import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest
import java.security.NoSuchAlgorithmException
import java.io.IOException

internal object UpdatePolicy {
    @JvmStatic
    fun versionCode(version: String): Int {
        if (!version.matches(Regex("(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)"))) {
            throw IllegalArgumentException("更新版本号无效。")
        }
        return try {
            val parts = version.split(".")
            val major = parts[0].toLong()
            val minor = parts[1].toLong()
            val patch = parts[2].toLong()
            if (major > 2100 || minor > 999 || patch > 999) {
                throw IllegalArgumentException("更新版本号超出范围。")
            }
            val code = major * 1000000 + minor * 1000 + patch
            if (code < 1 || code > 2100000000) {
                throw IllegalArgumentException("更新版本号超出范围。")
            }
            code.toInt()
        } catch (error: NumberFormatException) {
            throw IllegalArgumentException("更新版本号无效。", error)
        }
    }

    @JvmStatic
    @JvmOverloads
    fun validate(version: String, code: Long, url: String, hash: String, size: Long, testBaseUrl: String = "") {
        val expected = "https://github.com/syrizelink/OpenFic/releases/download/v$version/OpenFic-$version-android.apk"
        val expectedTest = if (testBaseUrl.isEmpty()) "" else "$testBaseUrl/OpenFic-$version-android-updatetest.apk"
        if (versionCode(version) != code.toInt() || !(expected == url || expectedTest == url) || 
            !hash.matches(Regex("[a-f0-9]{64}")) || size <= 0) {
            throw IllegalArgumentException("更新信息无效,请稍后重试。")
        }
    }

    @JvmStatic
    @Throws(IOException::class, NoSuchAlgorithmException::class)
    fun matches(file: File, hash: String, size: Long): Boolean {
        if (!file.isFile || file.length() != size) return false
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(65536)
            var count: Int
            while (input.read(buffer).also { count = it } != -1) {
                digest.update(buffer, 0, count)
            }
        }
        val actual = digest.digest().joinToString("") { "%02x".format(it) }
        return actual == hash
    }
}
