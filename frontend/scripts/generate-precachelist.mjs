import { readdirSync, statSync, writeFileSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const distDir = fileURLToPath(new URL("../dist", import.meta.url));

const EXCLUDE_FILES = new Set(["sw.js", "sw-precache.js"]);
const EXCLUDE_EXTS = new Set([".woff2", ".woff", ".ttf", ".otf", ".eot", ".map"]);

function walk(dir, acc) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      walk(full, acc);
    } else {
      acc.push(full);
    }
  }
  return acc;
}

const files = walk(distDir, []);
const precacheList = files
  .filter((f) => {
    const name = f.split(sep).pop();
    if (EXCLUDE_FILES.has(name)) {
      return false;
    }
    const dot = name.lastIndexOf(".");
    const ext = dot >= 0 ? name.slice(dot).toLowerCase() : "";
    return !EXCLUDE_EXTS.has(ext);
  })
  .map((f) => {
    const rel = relative(distDir, f).split(sep).join("/");
    return "/" + rel;
  })
  .sort();

const output = `self.__PRECACHE_LIST = ${JSON.stringify(precacheList, null, 2)};\n`;

writeFileSync(join(distDir, "sw-precache.js"), output);
console.log(`precache list generated: ${precacheList.length} entries`);
