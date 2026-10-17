import fs from "node:fs";
// Dedicated static preview for plugin E2E tests. Do not deploy as production hosting.
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.resolve(fileURLToPath(new URL("../dist/", import.meta.url)));
const backend = process.env.OPENFIC_E2E_BACKEND ?? "http://127.0.0.1:8011";
const port = Number(process.env.OPENFIC_E2E_PREVIEW_PORT ?? 9012);
const types = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".wasm": "application/wasm",
};
http
  .createServer((request, response) => {
    if (request.url === "/runtime-config.json") {
      response.setHeader("Content-Type", "application/json");
      response.setHeader("Cache-Control", "no-store");
      response.end(JSON.stringify({ backendBaseUrl: backend }));
      return;
    }
    let target;
    try {
      target = path.resolve(
        root,
        "." + decodeURIComponent(new URL(request.url, "http://localhost").pathname),
      );
    } catch {
      response.writeHead(400);
      response.end();
      return;
    }
    if (target !== root && !target.startsWith(root + path.sep)) {
      response.writeHead(403);
      response.end();
      return;
    }
    const file =
      fs.existsSync(target) && fs.statSync(target).isFile()
        ? target
        : path.join(root, "index.html");
    response.setHeader("Content-Type", types[path.extname(file)] ?? "application/octet-stream");
    fs.createReadStream(file)
      .on("error", () => {
        if (!response.headersSent) response.writeHead(404);
        response.end();
      })
      .pipe(response);
  })
  .listen(port, "127.0.0.1", () =>
    process.stdout.write(`Plugin preview: http://127.0.0.1:${port}\n`),
  );
