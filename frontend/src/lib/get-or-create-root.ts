import { createRoot, type Root } from "react-dom/client";

const ROOT_KEY = "__openficReactRoot";

interface RootContainer extends HTMLElement {
  [ROOT_KEY]?: Root;
}

export function getOrCreateRoot(
  container: HTMLElement,
  createRootImpl: (container: HTMLElement) => Root = createRoot
): Root {
  const rootContainer = container as RootContainer;

  if (!rootContainer[ROOT_KEY]) {
    rootContainer[ROOT_KEY] = createRootImpl(container);
  }

  return rootContainer[ROOT_KEY];
}
