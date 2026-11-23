import { Info } from "lucide-react";
import { useTranslation } from "react-i18next";

import { InfoTooltip } from "@/components";

interface PluginSourceInfoProps {
  names: string[];
}

export function PluginSourceInfo({ names }: PluginSourceInfoProps) {
  const { t } = useTranslation();
  if (names.length === 0) return null;
  const label = t("settings.pluginProvidedBy", {
    name: names.join(t("settings.pluginNamesSeparator")),
  });
  return (
    <InfoTooltip content={label}>
      <button
        type="button"
        className="advanced-settings-info-button"
        aria-label={label}
        data-slot="plugin-source-info"
      >
        <Info size={14} />
      </button>
    </InfoTooltip>
  );
}
