import { Box, Flex, Text } from "@radix-ui/themes";
import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { IndexSettingsSectionHeader } from "./index-settings-section-header";

const OVERVIEW_GRID_STYLE = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  gap: "var(--space-3)",
} as const;

interface IndexSettingsOverviewProps {
  embeddingConfigured: boolean;
  enabledProjects: number;
  indexUnits: number;
  indexed: number;
  pending: number;
  failed: number;
}

export function IndexSettingsOverview({
  embeddingConfigured,
  enabledProjects,
  indexUnits,
  indexed,
  pending,
  failed,
}: IndexSettingsOverviewProps) {
  const { t } = useTranslation();

  return (
    <Box className="index-settings-card">
      <Flex
        direction="column"
        gap="3"
      >
        <IndexSettingsSectionHeader
          title={t("index.overview")}
          action={
            !embeddingConfigured ? (
              <Flex
                align="center"
                gap="1"
              >
                <AlertTriangle
                  size={14}
                  color="var(--amber-9)"
                />
                <Text
                  size="1"
                  color="amber"
                >
                  {t("index.infoNotConfigured")}
                </Text>
              </Flex>
            ) : null
          }
        />
        <Box style={OVERVIEW_GRID_STYLE}>
          <InfoStat
            label={t("index.enabledProjects")}
            value={enabledProjects}
          />
          <InfoStat
            label={t("index.indexUnits")}
            value={indexUnits}
          />
          <InfoStat
            label={t("index.indexed")}
            value={indexed}
          />
          <InfoStat
            label={t("index.pending")}
            value={pending}
          />
          <InfoStat
            label={t("index.failed")}
            value={failed}
          />
        </Box>
      </Flex>
    </Box>
  );
}

function InfoStat({ label, value }: { label: string; value: number }) {
  return (
    <Flex
      direction="column"
      gap="1"
    >
      <Text
        size="1"
        color="gray"
      >
        {label}
      </Text>
      <Text
        size="3"
        weight="medium"
      >
        {value}
      </Text>
    </Flex>
  );
}
