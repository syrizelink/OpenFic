import { defineConfig } from "@farmfe/core";
import { fileURLToPath } from "node:url";

const setupPath = fileURLToPath(new URL("./src/setup-ui", import.meta.url));

export default defineConfig({
  compilation: {
    input: {
      setup: "./src/setup-ui/index.html",
    },
    output: {
      path: "./dist/setup-ui",
      publicPath: "/setup/",
      targetEnv: "browser-esnext",
    },
    resolve: {
      alias: {
        "@setup": setupPath,
      },
    },
  },
  plugins: ["@farmfe/plugin-react"],
});
