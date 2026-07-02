/**
 * MacroNodeView - 宏节点 React 视图组件
 */

import { NodeViewWrapper, type NodeViewProps } from "@tiptap/react";
import { BookOpen, Database, GitBranch } from "lucide-react";
import { useTranslation } from "react-i18next";
import "./macro-node.css";

const MACRO_ICONS: Record<string, React.ReactNode> = {
  getmem: <Database size={12} />,
  getlist: <BookOpen size={12} />,
  getworld: <BookOpen size={12} />,
  if: <GitBranch size={12} />,
  endif: <GitBranch size={12} />,
};

export function MacroNodeView({ node, selected }: NodeViewProps) {
  const { t } = useTranslation();
  const macroName = node.attrs.macroName as string;
  const macroRaw = node.attrs.macroRaw as string;

  const icon = MACRO_ICONS[macroName] || null;
  const labelKeyMap: Record<string, string> = {
    getmem: "promptChains.macroGetmem",
    getlist: "promptChains.macroGetlist",
    getworld: "promptChains.macroGetworld",
    if: "promptChains.macroIf",
    endif: "promptChains.macroEndIf",
  };
  const label = t(labelKeyMap[macroName] ?? macroName, { defaultValue: macroName });

  const getDisplayText = (): string => {
    try {
      const match = macroRaw.match(/\{\{(\w+)::(.+?)\}\}/);
      if (match) {
        return match[2];
      }
    } catch {
      // ignore
    }
    return macroRaw;
  };

  return (
    <NodeViewWrapper
      as="span"
      className={`macro-tag macro-${macroName} ${selected ? "selected" : ""}`}
      data-macro-name={macroName}
      data-macro-raw={macroRaw}
    >
      {icon && <span className="macro-icon">{icon}</span>}
      <span className="macro-label">{label}</span>
      <span className="macro-value">{getDisplayText()}</span>
    </NodeViewWrapper>
  );
}
