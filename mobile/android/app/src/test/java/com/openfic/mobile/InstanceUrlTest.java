package com.openfic.mobile;
import org.junit.Test;
import static org.junit.Assert.*;
public class InstanceUrlTest {
    @Test public void acceptsRemoteOriginsAndLanPorts() {
        assertEquals("https://example.com", InstanceUrl.normalize("https://EXAMPLE.com:443/"));
        assertEquals("http://192.168.1.8:8000", InstanceUrl.normalize("http://192.168.1.8:8000/"));
        assertEquals("https://[2001:db8::1]", InstanceUrl.normalize("https://[2001:db8::1]"));
    }
    @Test public void rejectsLocalCredentialsAndPaths() {
        for (String url : new String[]{"http://localhost", "http://127.0.0.1", "http://[::1]", "file:///tmp", "https://user:password@example.com", "https://example.com/api", "https://example.com?token=secret", "https://example.com#page", "https://example.com:65536"}) {
            assertThrows(url, IllegalArgumentException.class, () -> InstanceUrl.normalize(url));
        }
    }
}
