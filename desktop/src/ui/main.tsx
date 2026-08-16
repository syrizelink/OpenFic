import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/cascadia-code";
import "@fontsource-variable/fira-code";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource-variable/noto-sans-sc";
import "@fontsource-variable/noto-serif-sc";
import "@fontsource-variable/roboto-mono";
import "@fontsource-variable/source-code-pro";
import "@fontsource/ma-shan-zheng";
import "@fontsource/wdxl-lubrifont-sc";
import "@fontsource/zcool-kuaile";
import "@fontsource/zcool-xiaowei";
import { App } from "./app";
import "./i18n";
import { installShellErrorTelemetry } from "./telemetry";
import "../../../frontend/src/styles/index.css";
import "./styles.css";

installShellErrorTelemetry();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
