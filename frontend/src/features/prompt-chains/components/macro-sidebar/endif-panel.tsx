/**
 * EndIfPanel - endif 宏预览面板
 */

import { Box, Flex, Text, Code } from "@radix-ui/themes";
import { GitBranch } from "lucide-react";
import { useTranslation } from "react-i18next";

export function EndIfPanel() {
  const { t } = useTranslation();

  return (
    <Box>
      <Flex
        align="center"
        gap="2"
        mb="4"
      >
        <GitBranch
          size={16}
          style={{ color: "var(--green-9)" }}
        />
        <Text
          size="2"
          weight="medium"
        >
          {t("promptChains.macroEndIf")}
        </Text>
      </Flex>

      <Flex
        direction="column"
        gap="3"
      >
        <Box>
          <Text
            size="2"
            color="gray"
          >
            {t("promptChains.endIfDesc")}
          </Text>
        </Box>

        <Box>
          <Text
            size="2"
            weight="medium"
            mb="2"
          >
            {t("promptChains.example")}
          </Text>
          <Code size="1">
            {`{{if::show_content}}
这段内容会根据条件显示或隐藏
{{endif}}`}
          </Code>
        </Box>
      </Flex>
    </Box>
  );
}
