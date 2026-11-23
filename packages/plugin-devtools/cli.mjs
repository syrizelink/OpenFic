#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { scopeCSS } from "./css.mjs";
try {
  if (process.argv[2] !== "css") throw new Error("Usage: openfic-plugin-ui css [file.css|document.json] [--json]");
  const file = process.argv.slice(3).find(arg => !arg.startsWith("--"));
  const pairs = file ? [[file, file.endsWith(".json") ? JSON.parse(readFileSync(file, "utf8")).css ?? "" : readFileSync(file, "utf8")]] : JSON.parse(readFileSync(0, "utf8"));
  if (!Array.isArray(pairs)) throw new Error("Expected [filename, stylesheet] pairs");
  const diagnostics = [];
  for (const [path, css] of pairs) {
    if (typeof path !== "string" || typeof css !== "string") throw new Error("Invalid stylesheet input");
    for (const message of scopeCSS(css, "plugin-development-check").warnings)
      diagnostics.push({ code: "css.filtered", message, path, level: "warning" });
  }
  process.stdout.write(JSON.stringify({ diagnostics }, null, 2) + "\n");
} catch (error) {
  process.stderr.write(String(error.message) + "\n");
  process.exitCode = 1;
}
