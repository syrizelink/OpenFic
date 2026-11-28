import fs from "node:fs";
import { fileURLToPath } from "node:url";

import ts from "typescript";
const source = fileURLToPath(new URL("../../packages/plugin-devtools/src/css.ts", import.meta.url));
const target = fileURLToPath(new URL("../../packages/plugin-devtools/css.mjs", import.meta.url));
const output =
  "// Generated from src/css.ts; do not edit.\n" +
  ts.transpileModule(fs.readFileSync(source, "utf8"), {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ESNext,
      verbatimModuleSyntax: true,
    },
  }).outputText;
if (process.argv.includes("--check")) {
  if (fs.readFileSync(target, "utf8") !== output) throw new Error("Plugin CSS compiler is stale");
} else fs.writeFileSync(target, output);
