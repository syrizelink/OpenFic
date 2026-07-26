import { type Ref } from "react";

interface FrontendPageProps {
  webviewKey: number;
  partition: string;
  webviewRef: Ref<HTMLElement>;
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
