import assert from "node:assert/strict";
import { createServer } from "node:http";

import { app, net, session } from "electron";

import { waitForBackend } from "../../dist/main/health.js";
import { ensureAppProtocolForPartition, setRuntimeConfig } from "../../dist/main/protocol.js";
import { isNgrokUrl } from "../../dist/main/remote-url.js";

app.commandLine.appendSwitch(
  "host-resolver-rules",
  "MAP *.ngrok.io 127.0.0.1, MAP example.test 127.0.0.1",
);

const requests = [];
const server = createServer((request, response) => {
  requests.push({ url: request.url, headers: request.headers });
  if (request.url === "/redirect" || request.headers.host.startsWith("redirect-health.ngrok.io:")) {
    response.writeHead(302, {
      location: `http://example.test:${request.headers.host.split(":").at(-1)}/api/v1/health`,
    });
    response.end();
    return;
  }
  if (request.url === "/login") {
    response.setHeader("set-cookie", "openfic_auth=captured; Path=/; HttpOnly");
  }
  if (request.headers["ngrok-skip-browser-warning"] !== "1") {
    response.writeHead(200, { "content-type": "text/html" });
    response.end("<html>ngrok browser warning</html>");
    return;
  }
  response.writeHead(200, { "content-type": "application/json" });
  response.end(JSON.stringify({ status: "healthy", version: "smoke" }));
});
const otherServer = createServer(server.listeners("request")[0]);

async function smokeTestNgrok() {
  for (const domain of [
    "ngrok-free.app",
    "ngrok-free.dev",
    "ngrok.app",
    "ngrok.dev",
    "ngrok.pizza",
    "ngrok.io",
  ]) {
    for (const host of [domain, `openfic.${domain}`, `nested.openfic.${domain}`]) {
      assert.equal(isNgrokUrl(`https://${host.toUpperCase()}/api`), true, host);
      assert.equal(isNgrokUrl(`http://${host}:8080`), true, host);
    }
    for (const value of [
      `https://fake${domain}`,
      `https://${domain}.example.com`,
      `https://${domain}@example.com`,
      `https://user:password@${domain}`,
      `https://example.com/?url=${domain}`,
      `ftp://openfic.${domain}`,
    ]) {
      assert.equal(isNgrokUrl(value), false, value);
    }
  }
  for (const value of [
    "not a URL",
    "https://ngrok.com",
    "https://ngrok-free.pizza",
    "http://localhost",
    "http://127.0.0.1",
    "https://example.com",
  ]) {
    assert.equal(isNgrokUrl(value), false, value);
  }
  await app.whenReady();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  await new Promise((resolve) => otherServer.listen(0, "127.0.0.1", resolve));
  const baseUrl = `http://openfic.ngrok.io:${server.address().port}`;
  await net.fetch(`${baseUrl}/api/v1/health`).then(async (response) => {
    assert.match(await response.text(), /ngrok browser warning/);
  });
  assert.deepEqual(await waitForBackend(baseUrl, { timeoutMs: 1500 }), {
    status: "healthy",
    version: "smoke",
  });
  assert.equal(requests.at(-1).headers["ngrok-skip-browser-warning"], "1");

  const healthRedirectRequests = requests.length;
  await assert.rejects(
    waitForBackend(baseUrl.replace("openfic.ngrok.io", "redirect-health.ngrok.io"), {
      timeoutMs: 600,
    }),
    /health check timeout/,
  );
  assert.ok(
    requests
      .slice(healthRedirectRequests)
      .every(({ headers }) => headers.host.startsWith("redirect-health.ngrok.io:")),
    "health checks must not follow redirects or forward ngrok headers to another origin",
  );

  const partition = "ngrok-smoke";
  setRuntimeConfig({ backendBaseUrl: baseUrl });
  await ensureAppProtocolForPartition(partition);
  const targetSession = session.fromPartition(partition);
  await targetSession.fetch(`${baseUrl}/login`);
  await targetSession.cookies.set({
    url: baseUrl,
    name: "openfic_auth",
    value: "stored",
    httpOnly: true,
  });
  await targetSession.cookies.set({ url: baseUrl, name: "preference", value: "keep" });
  await targetSession.fetch(`${baseUrl}/api/v1/health`);
  assert.equal(requests.at(-1).headers["ngrok-skip-browser-warning"], "1");
  assert.match(requests.at(-1).headers.cookie, /(?:^|; )preference=keep(?:;|$)/);
  assert.match(requests.at(-1).headers.cookie, /(?:^|; )openfic_auth=stored(?:;|$)/);

  await targetSession.cookies.remove(baseUrl, "openfic_auth");
  await targetSession.cookies.set({ url: baseUrl, name: "preference", value: "fallback" });
  await targetSession.fetch(`${baseUrl}/api/v1/health`);
  assert.match(requests.at(-1).headers.cookie, /openfic_auth=captured/);
  assert.match(requests.at(-1).headers.cookie, /preference=fallback/);

  for (const url of [
    baseUrl.replace("openfic.ngrok.io", "other.ngrok.io"),
    baseUrl.replace("openfic.ngrok.io", "example.test"),
  ]) {
    await targetSession.fetch(`${url}/api/v1/health`);
    assert.equal(requests.at(-1).headers["ngrok-skip-browser-warning"], undefined, url);
    assert.doesNotMatch(requests.at(-1).headers.cookie ?? "", /openfic_auth=/, url);
  }
  await targetSession.fetch(`http://openfic.ngrok.io:${otherServer.address().port}/api/v1/health`);
  assert.equal(requests.at(-1).headers["ngrok-skip-browser-warning"], undefined, "different port");
  assert.doesNotMatch(
    requests.at(-1).headers.cookie ?? "",
    /openfic_auth=/,
    "no captured cookie on different port",
  );
  await targetSession.fetch(`${baseUrl}/redirect`);
  assert.equal(
    requests.at(-1).headers["ngrok-skip-browser-warning"],
    undefined,
    "cross-origin redirect",
  );
  await net.fetch(`${baseUrl}/api/v1/health`);
  assert.equal(
    requests.at(-1).headers["ngrok-skip-browser-warning"],
    undefined,
    "default session remains unchanged",
  );

  const plainUrl = baseUrl.replace("openfic.ngrok.io", "example.test");
  await assert.rejects(waitForBackend(plainUrl, { timeoutMs: 600 }), /health check timeout/);
  assert.equal(requests.at(-1).headers["ngrok-skip-browser-warning"], undefined);
  setRuntimeConfig({ backendBaseUrl: plainUrl });
  await targetSession.fetch(`${plainUrl}/api/v1/health`);
  assert.equal(
    requests.at(-1).headers["ngrok-skip-browser-warning"],
    undefined,
    "non-ngrok instance",
  );
  console.log(
    "ngrok smoke passed: domains, HTML interstitial, health JSON, exact origin, cookies, session isolation",
  );
}

void smokeTestNgrok()
  .then(
    () => 0,
    (error) => {
      console.error(error);
      return 1;
    },
  )
  .then(async (exitCode) => {
    server.closeAllConnections();
    otherServer.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
    await new Promise((resolve) => otherServer.close(resolve));
    app.exit(exitCode);
  });
