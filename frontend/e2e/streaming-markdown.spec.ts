import { expect, test } from "@playwright/test";

// Exercise the real renderer without needing a backend or an Agent session.
// External-store updates and a sibling timer reproduce the scheduling pressure
// behind Streamdown 2.5.0's maximum-update-depth / frozen-stream regressions.
const HARNESS = `<!doctype html><html><body><div id="root"></div>
<script type="module">
import RefreshRuntime from '/@react-refresh';
RefreshRuntime.injectIntoGlobalHook(window);
window.$RefreshReg$ = () => {};
window.$RefreshSig$ = () => (type) => type;
window.__vite_plugin_react_preamble_installed__ = true;
</script></body></html>`;

for (const scenario of ["paragraph", "blocks", "without-animation"] as const) {
  test(`long Markdown stream stays current without crashing: ${scenario}`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    await page.route("**/__streamdown_regression", (route) =>
      route.fulfill({ contentType: "text/html", body: HARNESS }),
    );
    await page.goto("/__streamdown_regression");
    await page.waitForFunction(() => "__vite_plugin_react_preamble_installed__" in window);

    const finalText = await page.evaluate(async (kind) => {
      // Use Vite's canonical dependency URLs (including its version query).
      // Importing a second URL for React would create a second hook dispatcher.
      const rendererPath = "/src/components/streaming-markdown.tsx";
      const appSource = await (await fetch("/src/main.tsx")).text();
      const rootSource = await (await fetch("/src/lib/get-or-create-root.ts")).text();
      const rendererSource = await (await fetch(rendererPath)).text();
      const dependencyUrl = (source: string, name: string) => {
        const url = source.match(new RegExp(`"([^"\\n]*/${name}\\.js\\?[^"\\n]+)"`))?.[1];
        if (!url) throw new Error(`Vite dependency URL missing: ${name}`);
        return url;
      };
      const reactPath = dependencyUrl(appSource, "react");
      const clientPath = dependencyUrl(rootSource, "react-dom_client");
      const streamdownPath = dependencyUrl(rendererSource, "streamdown");
      const React = (await import(reactPath)).default as typeof import("react");
      const { createRoot } = (await import(clientPath))
        .default as typeof import("react-dom/client");
      const { StreamingMarkdown } = (await import(rendererPath)) as {
        StreamingMarkdown: import("react").ComponentType<{ content: string; isStreaming: boolean }>;
      };
      const { Streamdown } = (await import(streamdownPath)) as typeof import("streamdown");
      const listeners = new Set<() => void>();
      let content = "";
      let streaming = true;
      const subscribe = (listener: () => void) => {
        listeners.add(listener);
        return () => listeners.delete(listener);
      };
      const getSnapshot = () => content;
      function SiblingTimer() {
        const [tick, setTick] = React.useState(0);
        React.useEffect(() => {
          const id = window.setInterval(() => setTick((value) => value + 1), 5);
          return () => window.clearInterval(id);
        }, []);
        return React.createElement("output", null, tick);
      }
      function Renderer() {
        const text = React.useSyncExternalStore(subscribe, getSnapshot);
        return kind === "without-animation"
          ? React.createElement(Streamdown, { isAnimating: streaming }, text)
          : React.createElement(StreamingMarkdown, { content: text, isStreaming: streaming });
      }
      const root = createRoot(document.getElementById("root")!);
      root.render(
        React.createElement(
          React.StrictMode,
          null,
          React.createElement(SiblingTimer),
          React.createElement("main", null, React.createElement(Renderer)),
        ),
      );
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      const sentence =
        "这是一个持续增长的思考块，检查长文本在流式更新时是否正常渲染以及是否发生更新深度崩溃。";
      const documentText =
        kind === "paragraph"
          ? sentence.repeat(300)
          : Array.from(
              { length: 120 },
              (_, index) => `## 第${index}段\n\n${sentence.repeat(3)}\n\n`,
            ).join("");
      const fullText = `${documentText}\n\nSTREAM_COMPLETE_270`;
      for (let end = 6; end < fullText.length; end += 6) {
        content = fullText.slice(0, end);
        listeners.forEach((listener) => listener());
        await new Promise((resolve) => window.setTimeout(resolve, 0));
        if (end > 1000 && end % 600 === 0) {
          const visibleText = document.querySelector("main")?.textContent ?? "";
          if (visibleText.length < end / 2) {
            throw new Error(`Stream stopped updating at character ${end}`);
          }
        }
      }
      content = fullText;
      streaming = false;
      listeners.forEach((listener) => listener());
      return fullText;
    }, scenario);

    expect(errors).toEqual([]);
    await expect(page.locator("main")).toContainText("STREAM_COMPLETE_270");
    const rendered = await page.locator("main").textContent();
    const expectedText = finalText.replace(/^## /gm, "").replace(/\s+/g, "");
    expect(rendered?.replace(/\s+/g, "")).toBe(expectedText);
    expect(errors).toEqual([]);
  });
}
