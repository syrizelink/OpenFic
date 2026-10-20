# @openfic/plugin-devtools

Shared PostCSS compiler and offline declarative CSS diagnostic CLI for OpenFic plugins. No React runtime is required. The host uses the same `./css` export; the package is currently local and has not been published to npm.

```sh
npm install --save-dev /path/to/OpenFic/packages/plugin-devtools
npx openfic-plugin-ui css ./example.css --json
```

The CSS command reports rules/properties the host rejects or filters; it does not lint arbitrary iframe CSS as if it were declarative CSS. The Python `openfic plugin check` CLI integrates this compiler when the executable is on PATH. In the source repository it also detects the frontend's installed copy. Without Node/the compiler, missing CSS coverage is reported explicitly.

The full package/AST/fixture/project-script checker, watcher and Inspector are provided by OpenFic's `openfic plugin` commands. See `docs/develop/plugin-devtools.md`. `--run-checks` executes author-provided code and must only be used on trusted sources.

Maintainers edit `src/css.ts`, then run `node frontend/scripts/generate-plugin-css.mjs` from the repository. `--check` verifies the generated `css.mjs`. Keep `css.d.mts` aligned with the exported signatures. Install the local dependency again after changing its shipped files; do not edit the generated module or create another CSS policy.
