import { inlineStyle as compileInlineStyle } from "@openfic/plugin-devtools/css";
import type { CSSProperties } from "react";

import type { UIProps } from "./declarative-schema";
export { scopeCSS, safeHref, safeCSSValue } from "@openfic/plugin-devtools/css";
export function inlineStyle(
  props: UIProps,
  animations: Map<string, string>,
  variables?: Set<string>,
): CSSProperties {
  return compileInlineStyle(props, animations, variables) as CSSProperties;
}
