import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { ChartPanel } from "./chart-panel";
import { MetricCard } from "./metric-card";
import {
  buildModelTokenTrendOption,
  buildModelTrendOption,
  buildRoundedDonutOption,
} from "../lib/dashboard-chart-options";
import type { DashboardStatsResponse } from "../lib/dashboard.types";

interface LlmDashboardTabProps {
  data: DashboardStatsResponse | undefined;
  isLoading: boolean;
  themeMode: "light" | "dark";
}

export function LlmDashboardTab({ data, isLoading, themeMode }: LlmDashboardTabProps) {
  const { t } = useTranslation();
  const callsOption = useMemo(() => buildModelTrendOption(data, "calls"), [data]);
  const tokenTrendOption = useMemo(() => buildModelTokenTrendOption(data), [data]);
  const modelCallsOption = useMemo(() => buildRoundedDonutOption(data?.byModel ?? [], "calls", t("dashboard.charts.modelCallsTitle")), [data?.byModel, t]);
  const modelTokensOption = useMemo(() => buildRoundedDonutOption(data?.byModel ?? [], "tokensTotal", t("dashboard.charts.modelTokensTitle")), [data?.byModel, t]);
  const latencyOption = useMemo(() => buildModelTrendOption(data, "avgLatencyMs"), [data]);
  const projectTokensOption = useMemo(() => buildRoundedDonutOption(data?.byProject ?? [], "tokensTotal", t("dashboard.charts.projectTokensTitle")), [data?.byProject, t]);
  const summary = data?.summary;

  return (
    <section className="dashboard-tab-panel">
      <section className="dashboard-metric-grid">
        <MetricCard
          label={t("dashboard.metrics.agentCalls")}
          value={summary?.callsTotal ?? 0}
          valueFormat={{ maximumFractionDigits: 0 }}
          hintParts={[
            { kind: "text", value: t("dashboard.metrics.completedPrefix") },
            { kind: "number", value: summary?.successTotal ?? 0, format: { maximumFractionDigits: 0 } },
            { kind: "text", value: t("dashboard.metrics.completedSuffix") },
          ]}
          isLoading={isLoading}
          hasValue={Boolean(summary)}
        />
        <MetricCard
          label={t("dashboard.metrics.tokenConsumption")}
          value={summary?.tokensTotal ?? 0}
          valueFormat={{ maximumFractionDigits: 0 }}
          hintParts={[
            { kind: "text", value: t("dashboard.metrics.inputPrefix") },
            { kind: "number", value: summary?.tokensInputTotal ?? 0, format: { maximumFractionDigits: 0 } },
            { kind: "text", value: t("dashboard.metrics.outputPrefix") },
            { kind: "number", value: summary?.tokensOutputTotal ?? 0, format: { maximumFractionDigits: 0 } },
          ]}
          isLoading={isLoading}
          hasValue={Boolean(summary)}
        />
        <MetricCard
          label={t("dashboard.metrics.avgLatency")}
          value={(summary?.avgLatencyMs ?? 0) / 1000}
          valueFormat={{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}
          valueSuffix=" s"
          hint={t("dashboard.metrics.avgLatencyHint")}
          isLoading={isLoading}
          hasValue={Boolean(summary)}
        />
        <MetricCard
          label={t("dashboard.metrics.firstToken")}
          value={(summary?.avgFirstTokenMs ?? 0) / 1000}
          valueFormat={{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}
          valueSuffix=" s"
          hint={t("dashboard.metrics.firstTokenHint")}
          isLoading={isLoading}
          hasValue={Boolean(summary)}
        />
      </section>
      <section className="dashboard-chart-grid dashboard-chart-grid-balanced dashboard-llm-chart-grid">
        <ChartPanel title={t("dashboard.charts.callTrend")} option={callsOption} isLoading={isLoading} themeMode={themeMode} size="wide" />
        <ChartPanel title={t("dashboard.charts.modelCallDistribution")} option={modelCallsOption} isLoading={isLoading} themeMode={themeMode} size="small" />
        <ChartPanel title={t("dashboard.charts.modelTokenDistribution")} option={modelTokensOption} isLoading={isLoading} themeMode={themeMode} size="small" />
        <ChartPanel title={t("dashboard.charts.tokenTrend")} option={tokenTrendOption} isLoading={isLoading} themeMode={themeMode} size="wide" />
        <ChartPanel title={t("dashboard.charts.latencyTrend")} option={latencyOption} isLoading={isLoading} themeMode={themeMode} size="wide" />
        <ChartPanel title={t("dashboard.charts.projectTokenDistribution")} option={projectTokensOption} isLoading={isLoading} themeMode={themeMode} size="small" />
      </section>
    </section>
  );
}
