import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import OpenFic from "../../../../packages/plugin-sdk";
export function App() {
  const [count, setCount] = useState(0);
  const [status, setStatus] = useState("Loading");
  useEffect(() => {
    void OpenFic.ready.then(async () => {
      setCount(await OpenFic.storage.get<number>("count", 0));
      setStatus("Ready");
    });
  }, []);
  return (
    <main style={{ color: "rgb(12, 34, 56)" }}>
      <h1>React SDK fixture</h1>
      <output>{count}</output>
      <button
        onClick={() => {
          const next = count + 1;
          setCount(next);
          void OpenFic.storage.set("count", next);
        }}
      >
        Increment
      </button>
      <button
        onClick={() => {
          void OpenFic.api.request("GET", "/projects").catch((e) => setStatus(e.message));
        }}
      >
        Try undeclared access
      </button>
      <p role="status">{status}</p>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
