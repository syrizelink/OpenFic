import { Theme } from "@radix-ui/themes";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { createRoot } from "react-dom/client";

import "@/i18n";

import "@/styles/index.css";
import "@/features/dashboard/pages/dashboard-page.css";
import { DashboardRecordsTab } from "@/features/dashboard/components/dashboard-records-tab";
import { LlmDashboardTab } from "@/features/dashboard/components/llm-dashboard-tab";
import {
  fetchLlmDashboardRecords,
  fetchLlmDashboardStats,
} from "@/features/dashboard/lib/dashboard-api";
import type { DashboardQueryParams } from "@/features/dashboard/lib/dashboard.types";

const query: DashboardQueryParams = {
  page: 1,
  pageSize: 20,
  sortBy: "created_at",
  sortOrder: "desc",
};
const client = new QueryClient({
  defaultOptions: { queries: { retry: false, staleTime: Infinity } },
});
export function Fixture() {
  const [tab, setTab] = useState("records");
  const records = useQuery({
    queryKey: ["records"],
    queryFn: () => fetchLlmDashboardRecords(query),
    enabled: tab === "records",
  });
  const stats = useQuery({
    queryKey: ["stats"],
    queryFn: () => fetchLlmDashboardStats(query),
    enabled: tab === "llm",
  });
  return (
    <Theme>
      <button onClick={() => setTab(tab === "records" ? "llm" : "records")}>Switch tab</button>
      {tab === "records" ? (
        <DashboardRecordsTab
          data={records.data}
          query={query}
          totalPages={1}
          isLoading={records.isFetching}
          updateQuery={() => {}}
        />
      ) : (
        <LlmDashboardTab
          data={stats.data}
          isLoading={stats.isFetching}
        />
      )}
    </Theme>
  );
}
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={client}>
    <Fixture />
  </QueryClientProvider>,
);
