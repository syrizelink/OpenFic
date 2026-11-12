import { Theme } from "@radix-ui/themes";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { createRoot } from "react-dom/client";

import { ChapterEditor } from "@/features/writing/components/chapter-editor";
import "@/i18n";

import "@/styles/index.css";
const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
export function Fixture() {
  const [locked, setLocked] = useState(false);
  return (
    <QueryClientProvider client={client}>
      <Theme>
        <button onClick={() => setLocked((value) => !value)}>Toggle Agent running</button>
        <ChapterEditor
          chapterId={new URLSearchParams(window.location.search).get("chapter")}
          isAgentLocked={locked}
        />
      </Theme>
    </QueryClientProvider>
  );
}
createRoot(document.getElementById("root")!).render(<Fixture />);
