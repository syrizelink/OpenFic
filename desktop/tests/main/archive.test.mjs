import assert from "node:assert/strict";
import { gzipSync } from "node:zlib";
import { mkdtemp, readFile, readlink, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { extractTarGz } from "../../dist/main/runtime/tar-extract.js";

function writeOctal(buffer, offset, length, value) {
  buffer.write(`${value.toString(8).padStart(length - 1, "0")}\0`, offset, length, "ascii");
}

function createTarGz(entries) {
  const blocks = [];

  for (const { content = "", linkname = "", name, type = "file" } of entries) {
    const contentBuffer = Buffer.isBuffer(content) ? content : Buffer.from(content);
    const header = Buffer.alloc(512);
    header.write(name, 0, 100, "utf8");
    writeOctal(header, 100, 8, type === "directory" ? 0o755 : 0o644);
    writeOctal(header, 108, 8, 0);
    writeOctal(header, 116, 8, 0);
    writeOctal(header, 124, 12, type === "file" ? contentBuffer.length : 0);
    writeOctal(header, 136, 12, 0);
    header.fill(0x20, 148, 156);
    header[156] = type === "symlink" ? 0x32 : 0x30;
    if (linkname) header.write(linkname, 157, 100, "utf8");
    header.write("ustar\0", 257, 6, "ascii");
    header.write("00", 263, 2, "ascii");
    writeOctal(header, 148, 8, header.reduce((sum, byte) => sum + byte, 0));

    const padding = Buffer.alloc((512 - (contentBuffer.length % 512)) % 512);
    blocks.push(header, contentBuffer, padding);
  }

  return gzipSync(Buffer.concat([...blocks, Buffer.alloc(1024)]));
}

function createPythonArchive() {
  return createTarGz([{ name: "python/python.exe", content: "portable python\n" }]);
}

function createPythonArchiveWithSymlink() {
  return createTarGz([
    { name: "python/python3.13", content: "portable python\n" },
    { name: "python/python3", type: "symlink", linkname: "python3.13" },
  ]);
}

test("falls back to the built-in extractor when tar is unavailable", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "openfic-archive-"));
  const archivePath = path.join(directory, "python.tar.gz");
  const outputDir = path.join(directory, "output");
  const originalPath = process.env.PATH;

  try {
    await writeFile(archivePath, createPythonArchive());
    process.env.PATH = "";

    await extractTarGz(archivePath, outputDir);

    assert.equal(await readFile(path.join(outputDir, "python", "python.exe"), "utf8"), "portable python\n");
  } finally {
    process.env.PATH = originalPath;
    await rm(directory, { recursive: true, force: true });
  }
});

test("preserves relative symbolic links when falling back to the built-in extractor", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "openfic-archive-"));
  const archivePath = path.join(directory, "python.tar.gz");
  const outputDir = path.join(directory, "output");
  const originalPath = process.env.PATH;

  try {
    await writeFile(archivePath, createPythonArchiveWithSymlink());
    process.env.PATH = "";

    await extractTarGz(archivePath, outputDir);

    assert.equal(await readlink(path.join(outputDir, "python", "python3")), "python3.13");
  } finally {
    process.env.PATH = originalPath;
    await rm(directory, { recursive: true, force: true });
  }
});

test("rejects archive entries outside the output directory", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "openfic-archive-"));
  const archivePath = path.join(directory, "python.tar.gz");
  const outputDir = path.join(directory, "output");
  const originalPath = process.env.PATH;

  try {
    await writeFile(archivePath, createTarGz([{ name: "../escape", content: "unsafe" }]));
    process.env.PATH = "";

    await assert.rejects(extractTarGz(archivePath, outputDir), /archive entry escapes output directory/);
  } finally {
    process.env.PATH = originalPath;
    await rm(directory, { recursive: true, force: true });
  }
});

test("uses the system tar when it is available", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "openfic-archive-"));
  const archivePath = path.join(directory, "python.tar.gz");
  const outputDir = path.join(directory, "output");

  try {
    await writeFile(archivePath, createPythonArchive());

    await extractTarGz(archivePath, outputDir);

    assert.equal(await readFile(path.join(outputDir, "python", "python.exe"), "utf8"), "portable python\n");
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("does not fall back when the system tar rejects an invalid archive", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "openfic-archive-"));
  const archivePath = path.join(directory, "invalid.tar.gz");
  const outputDir = path.join(directory, "output");

  try {
    await writeFile(archivePath, "not a gzip archive");

    await assert.rejects(extractTarGz(archivePath, outputDir), /tar exited with code/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
