import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ["react", "react-dom"],
    alias: {
      "@radix-ui/themes": fileURLToPath(
        new URL("./node_modules/@radix-ui/themes", import.meta.url),
      ),
    },
  },
});
