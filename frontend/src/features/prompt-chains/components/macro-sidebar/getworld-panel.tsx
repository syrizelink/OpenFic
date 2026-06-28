/**
 * GetworldPanel - getworld 宏说明面板
 */

import { Box, Callout, Code, Flex, Text } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import { BookOpen, Info } from "lucide-react";

export function GetworldPanel() {
  const { t } = useTranslation();

  return (
    <Box>
      <Flex align="center" gap="2" mb="4">
        <BookOpen size={16} style={{ color: "var(--cyan-9)" }} />
        <Text size="2" weight="medium">
          {t("promptChains.macroGetworld")}
        </Text>
      </Flex>

      <Callout.Root color="blue" mb="3">
        <Callout.Icon>
          <Info size={16} />
        </Callout.Icon>
        <Callout.Text size="1">
          {t("promptChains.getworldCompileHint")}
        </Callout.Text>
      </Callout.Root>

      <Text size="1" color="gray" as="p">
        {t("promptChains.getworldHint")}
      </Text>

      <Box mt="3">
        <Text size="1" weight="medium" mb="2">
          {t("promptChains.example")}
        </Text>
        <Code size="1">{"{{getworld}}"}</Code>
      </Box>
    </Box>
  );
}
