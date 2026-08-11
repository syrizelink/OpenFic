import { Flex, Text } from "@radix-ui/themes";
import { Check } from "lucide-react";
import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";

import {
  AGENT_COLOR_OPTIONS,
  AGENT_ICON_OPTIONS,
  getAgentColorVar,
  getAgentIconColor,
} from "@/lib/agent-branding";

interface AgentBrandingPickerProps {
  color: string | null | undefined;
  icon: string | null | undefined;
  onChange: (color: string | null, icon: string | null) => void;
  disabled?: boolean;
  labelStyle?: CSSProperties;
}

export function AgentBrandingPicker({
  color,
  icon,
  onChange,
  disabled = false,
  labelStyle,
}: AgentBrandingPickerProps) {
  const { t } = useTranslation();

  return (
    <Flex
      direction="column"
      gap="3"
      className="agent-branding-picker"
    >
      <Flex
        direction="column"
        gap="1"
      >
        <Text
          size="1"
          weight="medium"
          style={labelStyle}
        >
          {t("settings.agentsColor")}
        </Text>
        <Flex
          wrap="wrap"
          gap="2"
          role="radiogroup"
          aria-label={t("settings.agentsColor")}
        >
          {AGENT_COLOR_OPTIONS.map((option) => {
            const selected = option.value === color;
            return (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={selected}
                aria-label={t(option.labelKey)}
                title={t(option.labelKey)}
                disabled={disabled}
                className="agent-branding-swatch"
                data-selected={selected || undefined}
                style={{ background: getAgentColorVar(option.value) }}
                onClick={() => onChange(option.value, icon ?? null)}
              >
                {selected ? <Check size={12} /> : null}
              </button>
            );
          })}
        </Flex>
      </Flex>

      <Flex
        direction="column"
        gap="1"
      >
        <Text
          size="1"
          weight="medium"
          style={labelStyle}
        >
          {t("settings.agentsIcon")}
        </Text>
        <Flex
          wrap="wrap"
          gap="2"
          role="radiogroup"
          aria-label={t("settings.agentsIcon")}
        >
          {AGENT_ICON_OPTIONS.map((option) => {
            const Icon = option.icon;
            const selected = option.value === icon;
            return (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={selected}
                aria-label={t(option.labelKey)}
                title={t(option.labelKey)}
                disabled={disabled}
                className="agent-branding-icon-option"
                data-selected={selected || undefined}
                onClick={() => onChange(color ?? null, option.value)}
              >
                <Icon
                  size={16}
                  style={{ color: getAgentIconColor(color) }}
                />
              </button>
            );
          })}
        </Flex>
      </Flex>
    </Flex>
  );
}
