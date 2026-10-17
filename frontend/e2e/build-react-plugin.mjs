import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { build } from "vite-plus";
await build({
  configFile: false,
  root: fileURLToPath(new URL("./fixtures/plugin-react", import.meta.url)),
  plugins: [react()],
  base: "./",
  build: { outDir: process.argv[2], emptyOutDir: true, minify: true },
});
