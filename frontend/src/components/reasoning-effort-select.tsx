import { Brain } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { ReasoningEffort } from "@/lib/model.types";
import { REASONING_EFFORT_OPTIONS } from "@/lib/reasoning-effort";

import { SimpleSelect } from "./select";

import "./reasoning-effort-select.css";

export interface ReasoningEffortSelectProps {
  value: ReasoningEffort;
  onChange: (value: ReasoningEffort) => void;
  disabled?: boolean;
  size?: "1" | "2" | "3";
}

export function ReasoningEffortSelect({
  value,
  onChange,
  disabled = false,
  size = "2",
}: ReasoningEffortSelectProps) {
  const { t } = useTranslation();

  return (
    <SimpleSelect
      value={value}
      options={REASONING_EFFORT_OPTIONS}
      onChange={(nextValue) => onChange(nextValue as ReasoningEffort)}
      disabled={disabled}
      size={size}
      triggerPrefix={
        <Brain
          size={14}
          aria-hidden="true"
        />
      }
      triggerAriaLabel={t("assistant.thinkingTitle")}
      triggerClassName="reasoning-effort-select-trigger"
    />
  );
}
