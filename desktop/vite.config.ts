import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite-plus";

const desktopRoot = fileURLToPath(new URL(".", import.meta.url));
const repositoryRoot = fileURLToPath(new URL("..", import.meta.url));
const frontendPublicDir = fileURLToPath(new URL("../frontend/public", import.meta.url));
const uiRoot = fileURLToPath(new URL("./src/ui", import.meta.url));
const uiOutputDir = fileURLToPath(new URL("./dist/ui", import.meta.url));

export default defineConfig({
  root: uiRoot,
  publicDir: frontendPublicDir,
  plugins: [react()],
  build: {
    outDir: uiOutputDir,
    emptyOutDir: true,
    target: "esnext",
    rolldownOptions: {
      input: {
        ui: fileURLToPath(new URL("./src/ui/ui.html", import.meta.url)),
      },
    },
  },
  base: "./",
  server: {
    fs: {
      allow: [desktopRoot, repositoryRoot],
    },
  },
});
