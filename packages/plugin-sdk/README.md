# @openfic/plugin-sdk

Framework-independent types and optional module wrapper for the host SDK. Install from this directory (`file:.../packages/plugin-sdk`) or pack it with `npm pack`. No runtime dependencies. The host script `../../sdk.js` must load before your bundled application.

```ts
import OpenFic from '@openfic/plugin-sdk';
const context = await OpenFic.ready;
const chapter = await OpenFic.chapters.get(context.chapterId!);
```

The same API is available as `window.OpenFic` without installing a package. See `docs/develop/plugin-sdk-v2.md` and the runtime capability/OpenAPI catalogue. This directory is not published to npm by this task.


For native host UI, declare `renderer: "declarative"` with backend `render`/`action` commands. Exported `PluginView`, `UINode`, `UIProps`, `UIDocument`, `UIRenderRequest`, and `UIEventRequest` describe this data-only protocol; no browser SDK script is needed for these views. See `docs/develop/declarative-plugin-ui.md`. HTML/React/Vue applications continue to use the iframe SDK above.

Native UI includes 122 Radix Themes nodes and 10 project components (including model/project selectors). Unqualified names prefer project components; use `Radix.*` or `Project.*` explicitly. `UIDocument.css` supports custom styles constrained to the view and its portals. The host uses PostCSS to compile nesting, constrain selector targets and namespace animations; native CSS `@scope` and CSSOM replacement APIs are not required. Query `sdk.api.catalogue().ui` for per-component props and capabilities. See the installable `examples/plugins/declarative-showcase` and the native UI guide for restrictions. Declarative actions can return typed `UIActionResult` effects to use the same capability-checked editor and browser bridge (ordered calls and optional result continuation); Python handlers can call public SDK methods through `context.call`. Types are generated with `node frontend/scripts/generate-plugin-ui-catalog.mjs`; `--check` detects stale catalogue/types.
