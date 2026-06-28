import { useMemo } from "react";
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
  const callsOption = useMemo(() => buildModelTrendOption(data, "calls"), [data]);
  const tokenTrendOption = useMemo(() => buildModelTokenTrendOption(data), [data]);
  const modelCallsOption = useMemo(() => buildRoundedDonutOption(data?.byModel ?? [], "calls", "模型调用次数"), [data?.byModel]);
  const modelTokensOption = useMemo(() => buildRoundedDonutOption(data?.byModel ?? [], "tokensTotal", "模型 Token 消耗"), [data?.byModel]);
  const latencyOption = useMemo(() => buildModelTrendOption(data, "avgLatencyMs"), [data]);
  const projectTokensOption = useMemo(() => buildRoundedDonutOption(data?.byProject ?? [], "tokensTotal", "项目 Token 消耗"), [data?.byProject]);
  const summary = data?.summary;

  return (
    <section className="dashboard-tab-panel">
      <section className="dashboard-metric-grid">
        <MetricCard
          label="Agent 调用次数"
          value={summary?.callsTotal ?? 0}
          valueFormat={{ maximumFractionDigits: 0 }}
          hintParts={[
            { kind: "text", value: "完成 " },
            { kind: "number", value: summary?.successTotal ?? 0, format: { maximumFractionDigits: 0 } },
            { kind: "text", value: " 次" },
          ]}
          isLoading={isLoading}
          hasValue={Boolean(summary)}
        />
        <MetricCard
          label="Token 消耗"
          value={summary?.tokensTotal ?? 0}
          valueFormat={{ maximumFractionDigits: 0 }}
          hintParts={[
            { kind: "text", value: "输入 " },
            { kind: "number", value: summary?.tokensInputTotal ?? 0, format: { maximumFractionDigits: 0 } },
            { kind: "text", value: " / 输出 " },
            { kind: "number", value: summary?.tokensOutputTotal ?? 0, format: { maximumFractionDigits: 0 } },
          ]}
          isLoading={isLoading}
          hasValue={Boolean(summary)}
        />
        <MetricCard
          label="平均响应时间"
          value={(summary?.avgLatencyMs ?? 0) / 1000}
          valueFormat={{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}
          valueSuffix=" s"
          hint="完整模型响应耗时"
          isLoading={isLoading}
          hasValue={Boolean(summary)}
        />
        <MetricCard
          label="首字响应时间"
          value={(summary?.avgFirstTokenMs ?? 0) / 1000}
          valueFormat={{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}
          valueSuffix=" s"
          hint="流式响应首 token 延迟"
          isLoading={isLoading}
          hasValue={Boolean(summary)}
        />
      </section>
      <section className="dashboard-chart-grid dashboard-chart-grid-balanced dashboard-llm-chart-grid">
        <ChartPanel title="调用趋势" option={callsOption} isLoading={isLoading} themeMode={themeMode} size="wide" />
        <ChartPanel title="模型调用次数分布" option={modelCallsOption} isLoading={isLoading} themeMode={themeMode} size="small" />
        <ChartPanel title="模型消耗分布" option={modelTokensOption} isLoading={isLoading} themeMode={themeMode} size="small" />
        <ChartPanel title="消耗趋势" option={tokenTrendOption} isLoading={isLoading} themeMode={themeMode} size="wide" />
        <ChartPanel title="响应时间趋势" option={latencyOption} isLoading={isLoading} themeMode={themeMode} size="wide" />
        <ChartPanel title="总消耗分布" option={projectTokensOption} isLoading={isLoading} themeMode={themeMode} size="small" />
      </section>
    </section>
  );
}
