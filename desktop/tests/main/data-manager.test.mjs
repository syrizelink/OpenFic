import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {
  backupDataDir,
  arePathsEqual,
  doPathsOverlap,
  inspectDataDir,
  isPathWithin,
  migrateDataDir,
  removeDataDir,
  restoreDataDir,
} from "../../dist/main/data-manager.js";

async function createDataDir(base, name) {
  const dir = path.join(base, name);
  await mkdir(path.join(dir, "covers"), { recursive: true });
  await writeFile(path.join(dir, "openfic.db"), "sqlite", "utf8");
  await writeFile(path.join(dir, ".key"), "secret-key", "utf8");
  await writeFile(path.join(dir, "covers", "cover.png"), "png", "utf8");
  return dir;
}

test("inspects a data directory with recognizable OpenFic data", async () => {
  const base = await mkdtemp(path.join(os.tmpdir(), "openfic-data-"));
  try {
    const dir = await createDataDir(base, "src");
    const inspection = await inspectDataDir(dir);
    assert.equal(inspection.valid, true);
    assert.equal(inspection.hasData, true);
    assert.equal(inspection.entryCount, 3);
    assert.ok(inspection.sizeBytes > 0);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test("inspects an empty directory as having no data", async () => {
  const base = await mkdtemp(path.join(os.tmpdir(), "openfic-data-"));
  try {
    const dir = path.join(base, "empty");
    await mkdir(dir, { recursive: true });
    const inspection = await inspectDataDir(dir);
    assert.equal(inspection.valid, false);
    assert.equal(inspection.hasData, false);
    assert.equal(inspection.entryCount, 0);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test("backup and restore round-trips data directory contents", async () => {
  const base = await mkdtemp(path.join(os.tmpdir(), "openfic-data-"));
  try {
    const source = await createDataDir(base, "src");
    const archivePath = path.join(base, "backup.tar.gz");
    const restored = path.join(base, "restored");

    await backupDataDir(source, archivePath);
    assert.ok((await stat(archivePath)).size > 0);

    await restoreDataDir(archivePath, restored);
    assert.equal(await readFile(path.join(restored, "openfic.db"), "utf8"), "sqlite");
    assert.equal(await readFile(path.join(restored, ".key"), "utf8"), "secret-key");
    assert.equal(await readFile(path.join(restored, "covers", "cover.png"), "utf8"), "png");
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test("migrate copies data and preserves the source directory", async () => {
  const base = await mkdtemp(path.join(os.tmpdir(), "openfic-data-"));
  try {
    const source = await createDataDir(base, "src");
    const target = path.join(base, "target");

    await migrateDataDir(source, target);
    assert.equal(await readFile(path.join(target, "openfic.db"), "utf8"), "sqlite");
    assert.equal(await readFile(path.join(source, "openfic.db"), "utf8"), "sqlite");
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test("migrate cleans up the target directory when the source is missing", async () => {
  const base = await mkdtemp(path.join(os.tmpdir(), "openfic-data-"));
  try {
    const missingSource = path.join(base, "missing");
    const target = path.join(base, "target");

    await assert.rejects(migrateDataDir(missingSource, target));
    await assert.rejects(stat(target));
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test("removeDataDir deletes the directory recursively", async () => {
  const base = await mkdtemp(path.join(os.tmpdir(), "openfic-data-"));
  try {
    const dir = await createDataDir(base, "src");
    await removeDataDir(dir);
    await assert.rejects(stat(dir));
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test("path comparisons resolve aliases and parent-child overlap", async () => {
  const base = await mkdtemp(path.join(os.tmpdir(), "openfic-data-"));
  try {
    const parent = path.join(base, "parent");
    const child = path.join(parent, "child");
    await mkdir(child, { recursive: true });

    assert.equal(await arePathsEqual(parent, parent), true);
    assert.equal(await isPathWithin(parent, child), true);
    assert.equal(await doPathsOverlap(parent, child), true);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});
