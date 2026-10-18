# @openfic/plugin-sdk

Framework-independent types and optional module wrapper for the host SDK. Install from this directory (`file:.../packages/plugin-sdk`) or pack it with `npm pack`. No runtime dependencies. The host script `../../sdk.js` must load before your bundled application.

```ts
import OpenFic from '@openfic/plugin-sdk';
const context = await OpenFic.ready;
const chapter = await OpenFic.chapters.get(context.chapterId!);
```

The same API is available as `window.OpenFic` without installing a package. See `docs/develop/plugin-sdk-v2.md` and the runtime capability/OpenAPI catalogue. This directory is not published to npm by this task.


For native host UI, declare `renderer: "declarative"` with backend `render`/`action` commands. Exported `PluginView`, `UINode`, `UIProps`, `UIDocument`, `UIRenderRequest`, and `UIEventRequest` describe this data-only protocol; no browser SDK script is needed for these views. See `docs/develop/declarative-plugin-ui.md`. HTML/React/Vue applications continue to use the iframe SDK above.
