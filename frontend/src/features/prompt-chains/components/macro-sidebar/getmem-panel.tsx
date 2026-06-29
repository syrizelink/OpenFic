/**
 * GetmemPanel - getmem 宏预览面板（只读）
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { Box, Flex, Text, Button, ScrollArea, Callout } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import { Database, RefreshCw, AlertCircle } from "lucide-react";
import { Spinner } from "@/components";
import type { MacroNode } from "@/lib/macro";
import { parseMacro } from "@/lib/macro/parser";
import {
  fetchNearField,
  fetchMiddleField,
  fetchFarField,
  fetchLatestField,
} from "@/lib/api-client";

interface GetmemPanelProps {
  macro: MacroNode;
  workDir?: {
    projectId: string | null;
    chapterId: string | null;
  };
}

const FIELD_LABELS: Record<string, string> = {
  latest: "最新",
  far: "远场",
  middle: "中场",
  near: "近场",
};

const VALID_FIELDS = ["latest", "near", "middle", "far"];

export function GetmemPanel({ macro, workDir }: GetmemPanelProps) {
  const { t } = useTranslation();

  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const field = useMemo(() => {
    let args = macro.args;
    
    // 防御性编程：如果 args 为空但 raw 存在，尝试重新解析
    if ((!args || args.length === 0) && macro.raw) {
      try {
        // 构造一个临时的 MacroMatch 对象
        const node = parseMacro({
          body: macro.raw.slice(2, -2), // 去掉 {{ }}
          raw: macro.raw,
          start: 0,
          end: macro.raw.length,
        });
        args = node.args;
      } catch {
        // ignore parse error
      }
    }

    if (args && args.length >= 2) {
      const level1 = args[0];
      const level2 = args[1];
      if (level1.type === "identifier" && level1.value === "chapter") {
        if (level2.type === "identifier" && VALID_FIELDS.includes(level2.value as string)) {
          return level2.value as string;
        }
      }
    }
    return null;
  }, [macro.args, macro.raw]);

  const fetchContent = useCallback(async () => {
    if (!workDir?.projectId) {
      setError(t("promptChains.noWorkDirSet"));
      return;
    }

    if (!field) {
      setError(t("promptChains.invalidMacroArgs"));
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const chapterOrder = workDir.chapterId ? parseInt(workDir.chapterId, 10) : 1;

      let data: { content: string };
      if (field === "latest") {
        data = await fetchLatestField(workDir.projectId, chapterOrder);
      } else if (field === "near") {
        data = await fetchNearField(workDir.projectId, chapterOrder);
      } else if (field === "middle") {
        data = await fetchMiddleField(workDir.projectId, chapterOrder);
      } else if (field === "far") {
        data = await fetchFarField(workDir.projectId, chapterOrder);
      } else {
        throw new Error(`Unknown field: ${field}`);
      }

      setContent(data.content);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [workDir, field, t]);

  useEffect(() => {
    if (workDir?.projectId && field) {
      fetchContent();
    }
  }, [workDir, field, fetchContent]);

  return (
    <Box>
      <Flex align="center" gap="2" mb="4">
        <Database size={16} style={{ color: "var(--green-9)" }} />
        <Text size="2" weight="medium">
          {t("promptChains.macroGetmem")}
        </Text>
        {field && (
          <Text size="2" color="gray">
            ({FIELD_LABELS[field] || field})
          </Text>
        )}
      </Flex>

      {!workDir?.projectId && (
        <Callout.Root color="amber" mb="3">
          <Callout.Icon>
            <AlertCircle size={16} />
          </Callout.Icon>
          <Callout.Text size="1">
            {t("promptChains.noWorkDirSet")}
          </Callout.Text>
        </Callout.Root>
      )}

      {error && (
        <Callout.Root color="red" mb="3">
          <Callout.Icon>
            <AlertCircle size={16} />
          </Callout.Icon>
          <Callout.Text size="1">{error}</Callout.Text>
        </Callout.Root>
      )}

      {loading ? (
        <Flex align="center" justify="center" py="6">
          <Spinner size={18} />
        </Flex>
      ) : content !== null ? (
        <ScrollArea
          style={{
            maxHeight: "300px",
            border: "1px solid var(--gray-a5)",
            borderRadius: "6px",
            padding: "8px",
          }}
        >
          <Text
            size="1"
            style={{
              whiteSpace: "pre-wrap",
              fontFamily: 'var(--code-font-family, "JetBrainsMapleMono", ui-monospace, monospace)',
              fontSize: "14px",
              lineHeight: "1.6",
            }}
          >
            {content || t("promptChains.emptyContent")}
          </Text>
        </ScrollArea>
      ) : null}

      <Flex justify="end" mt="4">
        <Button
          size="2"
          variant="soft"
          onClick={fetchContent}
          disabled={loading || !workDir?.projectId}
        >
          <RefreshCw size={14} />
          {t("promptChains.refresh")}
        </Button>
      </Flex>
    </Box>
  );
}
