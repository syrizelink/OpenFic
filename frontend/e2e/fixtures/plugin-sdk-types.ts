// Consumer contract: native UI types require neither React nor @radix-ui in a plugin.
import type { OpenFicSDK, UIDocument, UIEventRequest } from "../../../packages/plugin-sdk";

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
