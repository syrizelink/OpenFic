// Run against tests.plugins.regression_app with disposable data only.
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const seedFile = process.argv[2];
if (!seedFile) throw new Error("Usage: node e2e/run-plugin-regression.mjs <seed.json>");
const seed = JSON.parse(readFileSync(seedFile, "utf8"));
const frontend = fileURLToPath(new URL("../", import.meta.url));
const evidence = process.env.OPENFIC_E2E_EVIDENCE_DIR;
const env = {
  ...process.env,
  OPENFIC_E2E_EMPTY_PROJECT_ID: seed.empty,
  OPENFIC_E2E_LARGE_PROJECT_ID: seed.large,
};
/** @type {Array<[string, string[]]>} */
const phases = [
  [
    "core",
    [
      "approval-resume",
      "cancel-flow",
      "compaction",
      "dashboard",
      "question-panel-collapse",
      "queueing",
      "writing-regression",
    ],
  ],
  ["plugins", ["official-mods", "plugin-sdk", "plugins", "declarative-plugins"]],
];
for (const [phase, names] of phases) {
  const phaseEnv = { ...env };
  if (phase === "plugins" && env.OPENFIC_E2E_PLUGIN_BASE_URL)
    phaseEnv.OPENFIC_E2E_BASE_URL = env.OPENFIC_E2E_PLUGIN_BASE_URL;
  if (evidence) phaseEnv.PLAYWRIGHT_JUNIT_OUTPUT_FILE = path.join(evidence, `browser-${phase}.xml`);
  const result = spawnSync(
    path.join(frontend, "node_modules/.bin/playwright"),
    ["test", ...names.map((name) => `e2e/${name}.spec.ts`), "--reporter=list,junit"],
    { cwd: frontend, env: phaseEnv, stdio: "inherit" },
  );
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
