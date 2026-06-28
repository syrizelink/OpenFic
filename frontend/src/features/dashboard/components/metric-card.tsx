import NumberFlow from "@number-flow/react";
import type { Format } from "@number-flow/react";
import type { ReactNode } from "react";
import { Card } from "@radix-ui/themes";

interface MetricCardHintPartNumber {
  format?: Format;
  kind: "number";
  suffix?: string;
  value: number;
}

interface MetricCardHintPartText {
  kind: "text";
  value: string;
}

type MetricCardHintPart = MetricCardHintPartText | MetricCardHintPartNumber;

interface MetricCardProps {
  cardClassName?: string;
  valueClassName?: string;
  label: string;
  value: number;
  hint?: ReactNode;
  hintParts?: MetricCardHintPart[];
  isLoading?: boolean;
  hasValue?: boolean;
  prefix?: ReactNode;
  valueFormat?: Format;
  valueSuffix?: string;
}

const flowTiming = {
  duration: 640,
  easing: "cubic-bezier(0.22, 1, 0.36, 1)",
};

export function MetricCard({
  cardClassName,
  valueClassName,
  label,
  value,
  hint,
  hintParts,
  isLoading = false,
  hasValue = true,
  prefix,
  valueFormat,
  valueSuffix,
}: MetricCardProps) {
  const displayValue = isLoading && !hasValue ? 0 : value;
  const resolvedHint = hintParts ? (
    <span>
      {hintParts.map((part, index) => part.kind === "text" ? (
        <span key={`${part.kind}-${index}`}>{part.value}</span>
      ) : (
        <NumberFlow
          key={`${part.kind}-${index}`}
          value={part.value}
          locales="zh-CN"
          format={part.format}
          suffix={part.suffix}
          transformTiming={flowTiming}
          spinTiming={flowTiming}
          opacityTiming={{ duration: 220, easing: "ease-out" }}
          className="dashboard-number-flow dashboard-number-flow-inline"
        />
      ))}
    </span>
  ) : hint;

  return (
    <Card className={["dashboard-metric-card", cardClassName].filter(Boolean).join(" ")}>
      <div className="dashboard-metric-label">{label}</div>
      <div
        className={["dashboard-metric-value", valueClassName].filter(Boolean).join(" ")}
        data-loading="false"
      >
        {prefix}
        <NumberFlow
          value={displayValue}
          locales="zh-CN"
          format={valueFormat}
          suffix={valueSuffix}
          transformTiming={flowTiming}
          spinTiming={flowTiming}
          opacityTiming={{ duration: 220, easing: "ease-out" }}
          className="dashboard-number-flow"
        />
      </div>
      {resolvedHint ? <div className="dashboard-metric-hint">{resolvedHint}</div> : null}
    </Card>
  );
}
