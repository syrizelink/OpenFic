import { createContext, useContext } from "react";

/** Undefined preserves ordinary application portals. Plugin views provide their own root. */
export const PortalContainerContext = createContext<HTMLElement | undefined>(undefined);
export function usePortalContainer() {
  return useContext(PortalContainerContext);
}
