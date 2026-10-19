# Native UI showcase

A Python-only plugin that renders actual OpenFic components and Radix Themes controls. No frontend build or iframe is needed.

```sh
python examples/plugins/build_package.py examples/plugins/declarative-showcase /tmp/declarative-showcase.zip
```

Install the ZIP from plugin management, confirm trust and enable it. Open **Native UI showcase** from the extensions sidebar. A small statusbar view demonstrates independent CSS and animation scopes. Create a configured model and a project to try the selectors; these request `models.read` and `projects.read` through the SDK gateway. Selections, form values and arrays persist in plugin storage.

The example demonstrates:

- Project components taking priority over Radix (`Spinner`, `Tooltip`, model/project selectors).
- Explicit `Radix.*` names, responsive Grid/Heading, compound TextField/Select/Tabs/Dialog/menus/popovers.
- Unit input, number stepper, searchable select, multi-select, radio and Slider commit events.
- Scoped stylesheet, custom properties, animation and portal styling.

See [the native UI guide](../../../docs/develop/declarative-plugin-ui.md) for the component catalogue, available props and CSS limits. Python plugins execute trusted backend code; install packages from authors you trust.
