import { Minus, Settings, Square, X } from "lucide-react";

interface DesktopHeaderProps {
  onShowSetup: () => void;
}

export function DesktopHeader({ onShowSetup }: DesktopHeaderProps) {
  return (
    <header className="desktop-header">
      <div className="desktop-titlebar-brand">OpenFic</div>
      <div className="desktop-titlebar-actions">
        <button className="titlebar-button" aria-label="设置" type="button" onClick={onShowSetup}>
          <Settings size={15} strokeWidth={2} />
        </button>
        <button className="titlebar-button" aria-label="最小化" type="button" onClick={() => void window.openficDesktop.minimizeWindow()}>
          <Minus size={15} strokeWidth={2} />
        </button>
        <button className="titlebar-button" aria-label="最大化" type="button" onClick={() => void window.openficDesktop.toggleMaximizeWindow()}>
          <Square size={14} strokeWidth={2} />
        </button>
        <button className="titlebar-button titlebar-button-close" aria-label="关闭" type="button" onClick={() => void window.openficDesktop.closeWindow()}>
          <X size={16} strokeWidth={2} />
        </button>
      </div>
    </header>
  );
}
