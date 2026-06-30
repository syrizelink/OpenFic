import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { SetupApp } from "./app";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SetupApp />
  </StrictMode>,
);
