import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite-plus";

const srcPath = fileURLToPath(new URL("./src", import.meta.url));
const frontendVersion = (
  JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8")) as {
    version: string;
  }
).version;

function cacheFontResponseHeaders(): Plugin {
  return {
    name: "cache-font-response-headers",
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        if (/\.(woff2?|ttf|otf|eot)(?:\?.*)?$/i.test(request.url ?? "")) {
          response.setHeader("Cache-Control", "public, max-age=3600");
        }
        next();
      });
    },
  };
}

export default defineConfig({
  define: {
    __OPENFIC_FRONTEND_VERSION__: JSON.stringify(frontendVersion),
  },
  plugins: [react(), cacheFontResponseHeaders()],
  resolve: {
    alias: {
      "@": srcPath,
    },
  },
  build: {
    outDir: "dist",
    target: "esnext",
  },
  server: {
    host: "127.0.0.1",
    port: 9000,
    cors: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/icons": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/socket.io": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
      "/covers": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/character-images": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
