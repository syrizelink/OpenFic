import { defineConfig } from "@farmfe/core";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const setupPath = fileURLToPath(new URL("./src/setup-ui", import.meta.url));
const require = createRequire(import.meta.url);
const reactPath = require.resolve("react");
const reactJsxRuntimePath = require.resolve("react/jsx-runtime");
const reactDomPath = require.resolve("react-dom");
const reactDomClientPath = require.resolve("react-dom/client");
const schedulerPath = require.resolve("scheduler");
const lucideReactPath = require.resolve("lucide-react");

export default defineConfig({
  compilation: {
    input: {
      setup: "./src/setup-ui/index.html",
    },
    output: {
      path: "./dist/setup-ui",
      publicPath: "./",
      targetEnv: "browser-esnext",
    },
    resolve: {
      symlinks: true,
      alias: {
        "@setup": setupPath,
        react: reactPath,
        "react/jsx-runtime": reactJsxRuntimePath,
        "react-dom": reactDomPath,
        "react-dom/client": reactDomClientPath,
        scheduler: schedulerPath,
        "lucide-react": lucideReactPath,
      },
    },
  },
  plugins: ["@farmfe/plugin-react"],
});
