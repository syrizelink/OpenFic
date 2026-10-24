package com.openfic.mobile

import org.junit.Assert.*
import org.junit.Test
import java.net.HttpURLConnection
import java.net.URL

class InstanceUrlTest {
    @Test
    fun recognizesOnlyHttpNgrokDomains() {
        for (domain in listOf(
            "ngrok.app", "ngrok.dev", "ngrok.pizza",
            "ngrok-free.app", "ngrok-free.dev", "ngrok.io",
        )) {
            assertTrue(domain, InstanceUrl.isNgrok("https://$domain"))
            assertTrue(domain, InstanceUrl.isNgrok("http://instance.$domain:8080/api/v1/health"))
            assertTrue(domain, InstanceUrl.isNgrok("https://INSTANCE.${domain.uppercase()}"))
            assertFalse(domain, InstanceUrl.isNgrok("https://evil-$domain"))
            assertFalse(domain, InstanceUrl.isNgrok("https://$domain.example.com"))
        }
        for (url in listOf(
            "https://example.com", "http://192.168.1.8:8000", "https://ngrok.com",
            "https://example.com/api/ngrok-free.app", "https://example.com?host=test.ngrok.io",
            "https://test.ngrok-free.app@example.com", "https://user@test.ngrok-free.app",
            "file://test.ngrok-free.app", "ftp://test.ngrok-free.app", "not a URL",
        )) {
            assertFalse(url, InstanceUrl.isNgrok(url))
        }
    }

    @Test
    fun addsNgrokHeaderWithoutChangingCookiesOrRedirectPolicy() {
        for (url in listOf(
            "https://test.ngrok-free.app/api/v1/health",
            "https://test.ngrok-free.dev/api/v1/export?format=zip",
            "https://test.ngrok.io/covers/image.png",
        )) {
            val connection = testConnection(url)
            connection.setRequestProperty("Cookie", "session=existing-session")
            connection.setRequestProperty("Accept", "application/json")
            connection.instanceFollowRedirects = false
            InstanceUrl.applyNgrokHeaders(connection)
            assertEquals("1", connection.getRequestProperty("ngrok-skip-browser-warning"))
            assertEquals("session=existing-session", connection.getRequestProperty("Cookie"))
            assertEquals("application/json", connection.getRequestProperty("Accept"))
            assertFalse(connection.instanceFollowRedirects)
        }
    }

    @Test
    fun doesNotAddHeadersToOtherServers() {
        for (url in listOf("https://example.com/api/v1/health", "http://192.168.1.8:8000")) {
            val connection = testConnection(url)
            InstanceUrl.applyNgrokHeaders(connection)
            assertNull(connection.getRequestProperty("ngrok-skip-browser-warning"))
        }
    }

    @Test
    fun usesNonBrowserUserAgentOnlyForNgrokInstances() {
        val browserUserAgent = "Mozilla/5.0 (Linux; Android 14; wv) Chrome/130.0"
        assertEquals(
            "OpenFic-Android/${BuildConfig.VERSION_NAME} (Android 14)",
            InstanceUrl.webViewUserAgent("https://test.ngrok-free.app", browserUserAgent),
        )
        assertEquals(browserUserAgent, InstanceUrl.webViewUserAgent("https://example.com", browserUserAgent))
        assertEquals(browserUserAgent, InstanceUrl.webViewUserAgent("http://192.168.1.8:8000", browserUserAgent))
    }

    private fun testConnection(url: String): HttpURLConnection = object : HttpURLConnection(URL(url)) {
        override fun connect() {}
        override fun disconnect() {}
        override fun usingProxy(): Boolean = false
    }

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
