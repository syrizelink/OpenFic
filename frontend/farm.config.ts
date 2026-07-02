import { defineConfig } from "@farmfe/core";
import type { Middleware } from 'koa';
import { fileURLToPath } from "node:url";

function addCacheToFonts(): Middleware {
    return async (ctx, next) => {
        await next();
        if (ctx.path && /\.(woff2?|ttf|otf|eot)$/i.test(ctx.path)) {
            ctx.set('Cache-Control', 'public, max-age=3600');
        }
    };
}

const srcPath = fileURLToPath(new URL("./src", import.meta.url));

export default defineConfig({
  compilation: {
    lazyCompilation: false,
    persistentCache: true,
    treeShaking: true,
    minify: true,
    define: {
      "import.meta.env.PROD": JSON.stringify(process.env.NODE_ENV === "production"),
    },
    input: {
      index: "./index.html"
    },
    output: {
      path: "./dist",
      publicPath: "/",
      targetEnv: "browser-esnext",
    },
    resolve: {
      alias: {
        "@": srcPath,
      },
    },
  },
  plugins: [
    "@farmfe/plugin-react"
  ],
  server: {
    host: "127.0.0.1",
    port: 9000,
    middlewares: [addCacheToFonts],
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
    },
  },
});
