/**
 * IfPanel - if 宏编辑面板
 */

import { useState } from "react";
import { Box, Flex, Text, TextField, Button, Code } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import { GitBranch } from "lucide-react";
import type { MacroNode } from "@/lib/macro";

interface IfPanelProps {
  macro: MacroNode;
  onUpdate?: (macroRaw: string) => void;
}

function getInitialVarName(macro: MacroNode): string {
  if (macro.args.length > 0) {
    const arg = macro.args[0];
    if (arg.type === "identifier") {
      return String(arg.value);
    }
  }
  return "";
}

export function IfPanel({ macro, onUpdate }: IfPanelProps) {
  const { t } = useTranslation();

  const [varName, setVarName] = useState<string>(() => getInitialVarName(macro));

  const handleApply = () => {
    if (!varName.trim()) return;
    const newRaw = `{{if::${varName.trim()}}}`;
    onUpdate?.(newRaw);
  };

  return (
    <Box>
      <Flex align="center" gap="2" mb="4">
        <GitBranch size={16} style={{ color: "var(--green-9)" }} />
        <Text size="2" weight="medium">
          {t("promptChains.macroIf")}
        </Text>
      </Flex>

      <Flex direction="column" gap="3">
        <Box>
          <Text size="2" weight="medium" mb="2">
            {t("promptChains.conditionVariable")}
          </Text>
          <TextField.Root
            value={varName}
            onChange={(e) => setVarName(e.target.value)}
            placeholder="show_content"
          />
          <Text size="1" color="gray" mt="1">
            {t("promptChains.ifVariableHint")}
          </Text>
        </Box>

        <Box>
          <Text size="2" weight="medium" mb="2">
            {t("promptChains.usage")}
          </Text>
          <Text size="2" color="gray" mb="2">
            {t("promptChains.ifUsageDesc")}
          </Text>
          <Code size="1">
            {`{{if::show}}
这段内容会显示
{{endif}}`}
          </Code>
        </Box>
      </Flex>

      <Flex justify="end" mt="4">
        <Button size="2" onClick={handleApply} disabled={!varName.trim()}>
          {t("promptChains.apply")}
        </Button>
      </Flex>
    </Box>
  );
}
