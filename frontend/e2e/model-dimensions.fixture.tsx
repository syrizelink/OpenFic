import { Theme } from "@radix-ui/themes";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { createRoot } from "react-dom/client";

import { AppShellContext } from "@/features/app-shell/components/app-shell-context";
import { ModelFormDialog } from "@/features/settings/components/model-form-dialog";
import i18n from "@/i18n";
import type { Model, ModelCreateRequest, ModelUpdateRequest } from "@/lib/model.types";

import "@/styles/index.css";

void i18n.changeLanguage("zh-CN");
const initial = new URLSearchParams(location.search).get("initial");
const model: Model = {
  id: "existing-model",
  name: "Embedding",
  remark: "",
  providerId: "provider",
  modelId: "embedding-model",
  taskType: "embedding",
  temperature: null,
  topP: null,
  topK: null,
  minP: null,
  topA: null,
  frequencyPenalty: null,
  presencePenalty: null,
  repetitionPenalty: null,
  maxTokens: null,
  contextLength: 128000,
  inputPrice: 0,
  outputPrice: 0,
  cacheReadPrice: 0,
  cacheWritePrice: 0,
  dimensions: initial === "manual" ? 1536 : initial === "filled" ? 6144 : null,
  isBuiltin: false,
  createdAt: "",
  updatedAt: "",
};
const noop = () => {};
const shell = {
  isMobile: false,
  isSidebarOpen: false,
  isSettingsOpen: true,
  openSidebar: noop,
  closeSidebar: noop,
  toggleSidebar: noop,
  openSettings: noop,
  closeSettings: noop,
  appendToAssistant: noop,
  isAssistantSidebarOpen: false,
  openAssistantSidebar: noop,
  closeAssistantSidebar: noop,
  registerAssistantSidebarHost: noop,
  clearAssistantSidebarHost: noop,
};
const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

export function Fixture() {
  const [open, setOpen] = useState(true);
  const [submitted, setSubmitted] = useState<ModelCreateRequest | ModelUpdateRequest>();
  return (
    <Theme>
      <AppShellContext.Provider value={shell}>
        <button onClick={() => setOpen(true)}>Open model</button>
        <ModelFormDialog
          open={open}
          onOpenChange={setOpen}
          model={model}
          models={[]}
          onSubmit={async (data) => {
            setSubmitted(data);
          }}
          isSubmitting={false}
          isAgentSettingsLocked={false}
        />
        <pre data-testid="submitted">{JSON.stringify(submitted)}</pre>
      </AppShellContext.Provider>
    </Theme>
  );
}

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={client}>
    <Fixture />
  </QueryClientProvider>,
);
