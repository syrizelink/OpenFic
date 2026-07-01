import { type RefObject } from "react";

interface FrontendPageProps {
  webviewKey: number;
  webviewRef: RefObject<HTMLElement | null>;
}

export function FrontendPage({ webviewKey, webviewRef }: FrontendPageProps) {
  return (
    <section className="content-page content-page-fill">
      <webview
        key={webviewKey}
        ref={webviewRef}
        className="frontend-webview"
        src="app://openfic/"
        preload={window.openficDesktop.frontendHostPreloadPath}
      />
    </section>
  );
}
