import { cp, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const source = fileURLToPath(new URL("../../frontend/dist/", import.meta.url));
const target = fileURLToPath(new URL("../dist/frontend/", import.meta.url));
await cp(source, target, { recursive: true });
const path = `${target}/index.html`;
let html = await readFile(path, "utf8");
// Bundled UI uses the remote origin; its assets update with the APK, not a service worker.
html = html.replace("<head>", "<head><script>window.openficMobileHost = true;</script>");
html = html.replace(
  "width=device-width, initial-scale=1.0",
  "width=device-width, initial-scale=1.0, viewport-fit=cover",
);
await writeFile(path, html);
