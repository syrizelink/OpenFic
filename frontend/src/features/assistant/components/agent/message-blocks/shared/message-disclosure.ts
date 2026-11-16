import { createContext, useContext, useState } from "react";

interface MessageDisclosureState {
  expandedIds: ReadonlySet<string>;
  onToggle: (messageId: string) => void;
}

export const MessageDisclosureContext = createContext<MessageDisclosureState | null>(null);

export function useMessageDisclosure(messageId: string) {
  const shared = useContext(MessageDisclosureContext);
  const [localExpanded, setLocalExpanded] = useState(false);
  const isExpanded = shared?.expandedIds.has(messageId) ?? localExpanded;
  const toggleExpanded = () => {
    if (shared) shared.onToggle(messageId);
    else setLocalExpanded((current) => !current);
  };
  return { isExpanded, toggleExpanded };
}
