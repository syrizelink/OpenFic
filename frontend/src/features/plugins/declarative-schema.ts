import catalogue from "../../../../backend/app/plugins/ui-catalog.json";

export type UIValue = null | boolean | number | string | UIValue[] | { [key: string]: UIValue };
export type UIProps = Record<string, UIValue>;
export type UINode =
  | null
  | boolean
  | number
  | string
  | { type: string; props: UIProps; children: UINode }
  | UINode[];
export interface UIDocument {
  version: 1;
  css: string;
  trees: { component: string; requestId: string; tree: UINode }[];
  panes: { id: string; title: string; focus: boolean; closeOnEscape: boolean }[];
  commands: { name: string }[];
}
export interface PropertyDefinition {
  type: string;
  values?: (string | number | boolean)[];
  responsive?: boolean;
}
export interface ComponentDefinition {
  props: Record<string, PropertyDefinition>;
  capabilities?: string[];
}
interface Catalogue {
  version: number;
  lucideIcons: string[];
  common: Record<string, PropertyDefinition>;
  radixCommon: Record<string, PropertyDefinition>;
  aliases: Record<string, string>;
  radix: Record<string, ComponentDefinition>;
  project: Record<string, ComponentDefinition>;
}
export const uiCatalogue = catalogue as unknown as Catalogue;
for (const [source, entries] of [
  ["radix", uiCatalogue.radix],
  ["project", uiCatalogue.project],
] as const)
  for (const definition of Object.values(entries))
    definition.props = {
      ...uiCatalogue.common,
      ...(source === "radix" ? uiCatalogue.radixCommon : {}),
      ...definition.props,
    };
export function resolveComponent(type: string) {
  if (uiCatalogue.project[type])
    return { source: "project", name: type, definition: uiCatalogue.project[type] };
  const target = uiCatalogue.aliases[type] ?? type;
  if (target.startsWith("Radix."))
    return {
      source: "radix",
      name: target.slice(6),
      definition: uiCatalogue.radix[target.slice(6)],
    };
  if (target.startsWith("Project."))
    return {
      source: "project",
      name: target.slice(8),
      definition: uiCatalogue.project[target.slice(8)],
    };
  if (uiCatalogue.project[target])
    return { source: "project", name: target, definition: uiCatalogue.project[target] };
  return { source: "radix", name: target, definition: uiCatalogue.radix[target] };
}
export type UIAction = (id: string, value?: UIValue, event?: string) => void;
