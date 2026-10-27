import { Theme } from "@radix-ui/themes";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { createRoot } from "react-dom/client";

import { ChapterEditor } from "@/features/writing/components/chapter-editor";
import "@/i18n";

import "@/styles/index.css";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

export function Fixture() {
  const [chapterId, setChapterId] = useState("first");
  return (
    <QueryClientProvider client={queryClient}>
      <Theme>
        <button onClick={() => setChapterId("first")}>First chapter</button>
        <button onClick={() => setChapterId("second")}>Second chapter</button>
        <button
          onClick={() => void queryClient.invalidateQueries({ queryKey: ["writing-editor"] })}
        >
          Refresh chapter
        </button>
        <ChapterEditor chapterId={chapterId} />
      </Theme>
    </QueryClientProvider>
  );
}

createRoot(document.getElementById("root")!).render(<Fixture />);
