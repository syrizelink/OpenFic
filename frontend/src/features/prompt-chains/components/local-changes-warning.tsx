import { Box, Flex, Text } from "@radix-ui/themes";
import { TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import "./local-changes-warning.css";

interface LocalChangesWarningProps {
  hasUnsavedChanges: boolean;
}

export function LocalChangesWarning({ hasUnsavedChanges }: LocalChangesWarningProps) {
  const { t } = useTranslation();

  if (!hasUnsavedChanges) return null;

  return (
    <Box
      className="prompt-chain-local-changes-warning"
      data-testid="prompt-chain-local-changes-warning"
    >
      <Flex
        align="start"
        gap="2"
      >
        <TriangleAlert
          aria-hidden="true"
          className="prompt-chain-local-changes-warning-icon"
          size={16}
        />
        <Text
          size="1"
          className="prompt-chain-local-changes-warning-text"
        >
          {t("promptChains.localChangesRequireVersionSave")}
        </Text>
      </Flex>
    </Box>
  );
}
