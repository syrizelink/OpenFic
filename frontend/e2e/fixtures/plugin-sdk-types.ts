// Consumer contract: native UI types require neither React nor @radix-ui in a plugin.
import type {
  OpenFicSDK,
  UIDocument,
  UIEventRequest,
  PluginView,
  PluginManifest,
  PluginDevelopmentConfig,
  UINode,
  UIPropsFor,
} from "../../../packages/plugin-sdk";

export const document = {
  css: ".settings { --gap: 8px; padding: var(--gap); }",
  tree: {
    type: "Grid",
    props: {
      className: "settings",
      columns: { initial: "1", md: "2" },
      style: { borderRadius: 8, "--color": "purple" },
      "aria-label": "Settings",
    },
    children: [
      { type: "ModelSelector", props: { taskType: "llm", onChange: "model" } },
      { type: "Radix.Spinner", props: { size: "2" } },
      { type: "Spinner", props: { size: 18 } },
      { type: "Icon", props: { name: "CloudUpload", size: 16, strokeWidth: 1.5 } },
      { type: "Slider", props: { value: [10, 20], onValueCommit: "range" } },
      {
        type: "Dialog.Root",
        children: { type: "Dialog.Trigger", children: { type: "Button", children: "Open" } },
      },
    ],
  },
} satisfies UIDocument;

export async function discover(sdk: OpenFicSDK) {
  const catalogue = await sdk.api.catalogue();
  return catalogue.ui.project.ModelIdSelect.capabilities;
}
export function eventValue(event: UIEventRequest) {
  return event.value;
}

export const editorView = {
  id: "sync",
  title: "Sync",
  slot: "editor.toolbar",
  icon: "CloudUpload",
  presentation: "popover",
  renderer: "declarative",
  render: "ui.render",
  action: "ui.action",
} satisfies PluginView;

// Component-specific props must stay correlated with type, including aliases.
const strictButton: UINode = {
  type: "Button",
  props: { size: "2", onPress: "save" },
  children: "Save",
};
// @ts-expect-error Image.asset is not a Button property.
const badButton: UINode = { type: "Button", props: { asset: "assets/a.png" } };
// @ts-expect-error Event handlers are IDs, not executable functions.
const badHandler: UINode = { type: "Button", props: { onPress: () => {} } };
const imageProps: UIPropsFor<"Project.Image"> = {
  asset: "assets/a.png",
  alt: "Asset",
  fit: "cover",
};
void [strictButton, badButton, badHandler, imageProps];

export const manifest = {
  id: "typed-example",
  name: "Typed example",
  version: "1.0.0",
  api_version: 1,
  entry: "src/plugin.py",
  resources: ["assets", "dist/panel"],
  capabilities: ["ui"],
  views: [editorView],
} satisfies PluginManifest;
export const development = {
  fixtures: [{ view: "sync", file: "fixtures/sync.json" }],
  package: { include: ["src", "assets", "dist/panel"], exclude: ["src/*.test.py"] },
} satisfies PluginDevelopmentConfig;
