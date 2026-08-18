import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
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
