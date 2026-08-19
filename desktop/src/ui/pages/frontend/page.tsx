import { type Ref } from "react";

export interface FrontendWebviewElement extends HTMLElement {
  canGoBack: () => boolean;
  goBack: () => void;
  canGoForward: () => boolean;
  goForward: () => void;
  send: (channel: string, ...args: unknown[]) => void;
}

interface FrontendPageProps {
  webviewKey: number;
  partition: string;
  webviewRef: Ref<FrontendWebviewElement>;
}

export function FrontendPage({ webviewKey, partition, webviewRef }: FrontendPageProps) {
  return (
    <section className="content-page content-page-fill">
      <webview
        key={webviewKey}
        ref={webviewRef}
        className="frontend-webview"
        src="app://openfic/"
        partition={partition}
        preload={window.openficDesktop.frontendHostPreloadPath}
      />
    </section>
  );
}
