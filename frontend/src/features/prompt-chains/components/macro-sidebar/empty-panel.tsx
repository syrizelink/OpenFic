/**
 * EmptyPanel - 空状态面板
 */

import { Flex, Text } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import { MousePointerClick } from "lucide-react";

export function EmptyPanel() {
  const { t } = useTranslation();

  return (
    <Flex
      direction="column"
      align="center"
      justify="center"
      gap="3"
      style={{
        height: "200px",
        color: "var(--gray-a9)",
      }}
    >
      <MousePointerClick size={32} />
      <Text size="2">{t("promptChains.selectMacroToEdit")}</Text>
    </Flex>
  );
}
