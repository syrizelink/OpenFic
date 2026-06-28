/**
 * GetlistPanel - getlist 宏说明面板
 */

import { Box, Code, Flex, Text } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import { BookOpen } from "lucide-react";

export function GetlistPanel() {
  const { t } = useTranslation();

  return (
    <Box>
      <Flex align="center" gap="2" mb="4">
        <BookOpen size={16} style={{ color: "var(--cyan-9)" }} />
        <Text size="2" weight="medium">
          {t("promptChains.macroGetlist")}
        </Text>
      </Flex>

      <Text size="1" color="gray" as="p">
        {t("promptChains.getlistHint")}
      </Text>

      <Box mt="3">
        <Text size="1" weight="medium" mb="2">
          {t("promptChains.example")}
        </Text>
        <Code size="1">{"{{getlist}}"}</Code>
      </Box>
    </Box>
  );
}
