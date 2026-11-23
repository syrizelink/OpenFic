# @openfic/plugin-sdk

Framework-independent types and optional module wrapper for the host SDK. Install from this directory (`file:.../packages/plugin-sdk`) or pack it with `npm pack`. No runtime dependencies. The host injects its SDK before the iframe application scripts; do not hardcode sdk.js paths.

```ts
import OpenFic from '@openfic/plugin-sdk';
const context = await OpenFic.ready;
const chapter = await OpenFic.chapters.get(context.chapterId!);
```

The same API is available as `window.OpenFic` without installing a package. Runtime capabilities are available through the OpenAPI catalogue. This directory is not published to npm by this task.


A plugin has one optional Python `entry` and explicitly declared public `resources`; all paths are relative to plugin.json. Neither backend/ nor frontend/ is required. Exported `PluginManifest` and `PluginDevelopmentConfig` describe the package and development configuration.

For native host UI, declare `renderer: "declarative"` with backend `render`/`action` commands. Exported `PluginView`, `UINode`, `UIProps`, `UIDocument`, `UIRenderRequest`, and `UIEventRequest` describe this data-only protocol; no browser SDK script is needed for these views. HTML/React/Vue applications continue to use the iframe SDK above.

Native UI includes 122 Radix Themes nodes and 13 project components (including model/project selectors). Unqualified names prefer project components; use `Radix.*` or `Project.*` explicitly. `UIDocument.css` supports custom styles constrained to the view and its portals. The host uses PostCSS to compile nesting, constrain selector targets and namespace animations; native CSS `@scope` and CSSOM replacement APIs are not required. Query `sdk.api.catalogue().ui` for per-component props and capabilities. Declarative actions can return typed `UIActionResult` effects to use the same capability-checked editor and browser bridge (ordered calls and optional result continuation); Python handlers can call public SDK methods through `context.call`. Types are generated with `node frontend/scripts/generate-plugin-ui-catalog.mjs`; `--check` detects stale catalogue/types.

`editor.toolbar` contributes compact action buttons inside the chapter/note toolbar. Actions can explicitly open an `app.overlay` dialog or popover using `ui.openOverlay`; popovers require an anchor, available as `context.anchor` for toolbar and status bar actions. Declare both `ui` and `ui.overlay` capabilities. `PluginView.icon` names a host Lucide icon. Declarative trees support `Icon` / `LucideIcon` with `name`, `size`, `color`, `strokeWidth`, `absoluteStrokeWidth` and accessible labels. Discover the installed icon names in `ui.lucideIcons`; the SDK exports `UIIconName`.

UINode correlates each component name with its props; use `UIPropsFor<C>` / `UIComponentPropsMap` for precise props. The generic UIProps remains for tooling. The local @openfic/plugin-devtools package shares the host CSS compiler; OpenFic CLI provides check/pack.
