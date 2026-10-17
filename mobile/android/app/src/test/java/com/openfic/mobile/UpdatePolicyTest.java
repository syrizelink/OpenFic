package com.openfic.mobile;

import org.junit.Test;
import static org.junit.Assert.*;
import java.io.File;
import java.nio.file.Files;

public class UpdatePolicyTest {
    @Test public void stableVersionsAreOrderedAndBounded() {
        assertEquals(12001, UpdatePolicy.versionCode("0.12.1"));
        assertTrue(UpdatePolicy.versionCode("1.0.0") > UpdatePolicy.versionCode("0.999.999"));
        for (String version : new String[]{"01.2.3", "1.0.0-beta.1", "1.1000.0", "1.0.1000", "2101.0.0"}) {
            assertThrows(IllegalArgumentException.class, () -> UpdatePolicy.versionCode(version));
        }
    }

    @Test public void onlyExactOfficialReleaseAssetsAreAccepted() {
        String url = "https://github.com/syrizelink/OpenFic/releases/download/v0.12.2/OpenFic-0.12.2-android.apk";
        String hash = "a".repeat(64);
        UpdatePolicy.validate("0.12.2", 12002, url, hash, 100);
        for (String bad : new String[]{url.replace("https:", "http:"), url + "?x=1", url.replace("OpenFic/releases", "other/releases"), url.replace("v0.12.2/", "v0.12.1/")}) {
            assertThrows(IllegalArgumentException.class, () -> UpdatePolicy.validate("0.12.2", 12002, bad, hash, 100));
        }
        assertThrows(IllegalArgumentException.class, () -> UpdatePolicy.validate("0.12.2", 12001, url, hash, 100));
        assertThrows(IllegalArgumentException.class, () -> UpdatePolicy.validate("0.12.2", 12002, url, "bad", 100));
        assertThrows(IllegalArgumentException.class, () -> UpdatePolicy.validate("0.12.2", 12002, url, hash, 0));
    }

    @Test public void corruptOrTruncatedDownloadsCannotBeInstalled() throws Exception {
        File file = File.createTempFile("openfic-update", ".apk");
        try {
            Files.write(file.toPath(), new byte[]{97, 98, 99});
            String hash = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
            assertTrue(UpdatePolicy.matches(file, hash, 3));
            assertFalse(UpdatePolicy.matches(file, hash, 4));
            assertFalse(UpdatePolicy.matches(file, "0".repeat(64), 3));
        } finally {
            Files.deleteIfExists(file.toPath());
        }
    }
}
