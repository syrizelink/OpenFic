package com.openfic.mobile

import org.junit.Assert.*
import org.junit.Test

class InstanceUrlTest {
    @Test
    fun acceptsRemoteOriginsAndLanPorts() {
        assertEquals("https://example.com", InstanceUrl.normalize("https://EXAMPLE.com:443/"))
        assertEquals("http://192.168.1.8:8000", InstanceUrl.normalize("http://192.168.1.8:8000/"))
        assertEquals("https://[2001:db8::1]", InstanceUrl.normalize("https://[2001:db8::1]"))
    }

    @Test
    fun rejectsLocalCredentialsAndPaths() {
        val invalidUrls = arrayOf(
            "http://localhost",
            "http://127.0.0.1",
            "http://[::1]",
            "file:///tmp",
            "https://user:password@example.com",
            "https://example.com/api",
            "https://example.com?token=secret",
            "https://example.com#page",
            "https://example.com:65536"
        )
        
        for (url in invalidUrls) {
            assertThrows(url, IllegalArgumentException::class.java) {
                InstanceUrl.normalize(url)
            }
        }
    }
}
