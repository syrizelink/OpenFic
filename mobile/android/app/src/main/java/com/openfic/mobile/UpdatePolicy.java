package com.openfic.mobile;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

final class UpdatePolicy {
    static int versionCode(String version) {
        if (!version.matches("(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)")) {
            throw new IllegalArgumentException("更新版本号无效。");
        }
        try {
            String[] parts = version.split("\\.");
            long major = Long.parseLong(parts[0]);
            long minor = Long.parseLong(parts[1]);
            long patch = Long.parseLong(parts[2]);
            if (major > 2100 || minor > 999 || patch > 999) throw new IllegalArgumentException("更新版本号超出范围。");
            long code = major * 1000000 + minor * 1000 + patch;
            if (code < 1 || code > 2100000000) throw new IllegalArgumentException("更新版本号超出范围。");
            return (int) code;
        } catch (NumberFormatException error) {
            throw new IllegalArgumentException("更新版本号无效。", error);
        }
    }

    static void validate(String version, long code, String url, String hash, long size) {
        validate(version, code, url, hash, size, "");
    }

    static void validate(String version, long code, String url, String hash, long size, String testBaseUrl) {
        String expected = "https://github.com/syrizelink/OpenFic/releases/download/v" + version + "/OpenFic-" + version + "-android.apk";
        String expectedTest = testBaseUrl.isEmpty() ? "" : testBaseUrl + "/OpenFic-" + version + "-android-updatetest.apk";
        if (versionCode(version) != code || !(expected.equals(url) || expectedTest.equals(url)) || !hash.matches("[a-f0-9]{64}") || size <= 0) {
            throw new IllegalArgumentException("更新信息无效，请稍后重试。");
        }
    }

    static boolean matches(File file, String hash, long size) throws IOException, NoSuchAlgorithmException {
        if (!file.isFile() || file.length() != size) return false;
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (FileInputStream input = new FileInputStream(file)) {
            byte[] buffer = new byte[65536];
            int count;
            while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
        }
        StringBuilder actual = new StringBuilder();
        for (byte value : digest.digest()) actual.append(String.format(java.util.Locale.ROOT, "%02x", value & 0xff));
        return actual.toString().equals(hash);
    }
}
