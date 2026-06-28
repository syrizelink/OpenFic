/**
 * VersionListDialog Component
 *
 * 版本列表弹窗 - 增强版，支持差异对比
 */

import { useState } from "react";
import { Dialog, Flex, Text, Button, IconButton, Box, ScrollArea } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import { Check, GitCompare } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { zhCN, enUS } from "date-fns/locale";
import { VersionDiffDialog } from "./version-diff-dialog";
import type { PromptChainVersion } from "@/lib/prompt-chain.types";

interface VersionListDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  versions: PromptChainVersion[];
  currentVersionId: string | null;
  onSelectVersion: (versionId: string) => void;
  modeName: string;
  taskName: string;
  agentName: string | null;
}

export function VersionListDialog({
  open,
  onOpenChange,
  versions,
  currentVersionId,
  onSelectVersion,
  modeName,
  taskName,
  agentName,
}: VersionListDialogProps) {
  const { t, i18n } = useTranslation();
  
  // 差异对比状态
  const [diffDialogOpen, setDiffDialogOpen] = useState(false);
  const [compareVersionId, setCompareVersionId] = useState<string | null>(null);
  
  // 根据当前语言获取 date-fns locale
  const getDateLocale = () => {
    const language = i18n.language;
    switch (language) {
      case "zh-CN":
        return zhCN;
      case "en":
        return enUS;
      default:
        return zhCN;
    }
  };

  // 打开差异对比对话框
  const handleOpenDiff = (versionId: string) => {
    if (!currentVersionId) return;
    setCompareVersionId(versionId);
    setDiffDialogOpen(true);
  };

  return (
    <>
      <Dialog.Root open={open} onOpenChange={onOpenChange}>
        <Dialog.Content style={{ maxWidth: "700px" }}>
          <Dialog.Title>{t("promptChains.versionHistory")}</Dialog.Title>
          <Dialog.Description size="2" mb="4">
            {t("promptChains.selectVersion")}
          </Dialog.Description>

          <ScrollArea style={{ maxHeight: "500px" }}>
            <Flex direction="column" gap="2">
              {versions.length === 0 ? (
                <Box
                  p="6"
                  style={{
                    textAlign: "center",
                    color: "var(--gray-a9)",
                    border: "1px dashed var(--gray-a5)",
                    borderRadius: "var(--radius-2)",
                  }}
                >
                  <Text size="2">{t("promptChains.noVersions")}</Text>
                </Box>
              ) : (
                versions.map((version) => {
                  const isCurrent = version.id === currentVersionId;
                  const timeAgo = formatDistanceToNow(new Date(version.createdAt), {
                    addSuffix: true,
                    locale: getDateLocale(),
                  });

                  // 找到父版本
                  const parentVersion = version.parentVersionId
                    ? versions.find((v) => v.id === version.parentVersionId)
                    : null;

                  return (
                    <Box
                      key={version.id}
                      p="3"
                      style={{
                        border: `1px solid ${
                          isCurrent ? "var(--accent-9)" : "var(--gray-a5)"
                        }`,
                        borderRadius: "var(--radius-2)",
                        background: isCurrent
                          ? "var(--accent-a2)"
                          : "var(--color-background)",
                        opacity: version.isActive ? 1 : 0.5,
                      }}
                    >
                      <Flex justify="between" align="start">
                        {/* 版本信息 */}
                        <Flex direction="column" gap="1" style={{ flex: 1 }}>
                          <Flex align="center" gap="2">
                            <Text size="3" weight="bold">
                              v{version.versionNumber}
                            </Text>
                            <Text size="2" color="gray">
                              {version.versionHash}
                            </Text>
                            {!version.isActive && (
                              <Text size="1" color="orange">
                                {t("promptChains.truncated")}
                              </Text>
                            )}
                            {isCurrent && (
                              <Text size="1" color="blue">
                                {t("promptChains.currentVersion")}
                              </Text>
                            )}
                          </Flex>

                          {parentVersion && (
                            <Text size="1" color="gray">
                              {t("promptChains.basedOn")} v{parentVersion.versionNumber}
                            </Text>
                          )}

                          {version.note && (
                            <Text size="2" style={{ marginTop: "4px" }}>
                              {version.note}
                            </Text>
                          )}

                          <Text size="1" color="gray" style={{ marginTop: "4px" }}>
                            {timeAgo}
                          </Text>
                        </Flex>

                        {/* 操作按钮 */}
                        <Flex gap="1">
                          {/* Diff按钮 */}
                          {currentVersionId && version.id !== currentVersionId && (
                            <IconButton
                              variant="ghost"
                              size="1"
                              onClick={() => handleOpenDiff(version.id)}
                              title={t("promptChains.diffWithCurrent")}
                            >
                              <GitCompare size={14} />
                            </IconButton>
                          )}

                          {/* 选择按钮 */}
                          {!isCurrent && (
                            <Button
                              variant="soft"
                              size="1"
                              onClick={() => onSelectVersion(version.id)}
                            >
                              <Check size={14} />
                              {t("promptChains.select")}
                            </Button>
                          )}
                        </Flex>
                      </Flex>
                    </Box>
                  );
                })
              )}
            </Flex>
          </ScrollArea>

          <Flex gap="3" mt="4" justify="end">
            <Dialog.Close>
              <Button variant="soft" color="gray">
                {t("promptChains.close")}
              </Button>
            </Dialog.Close>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>

      {/* 差异对比对话框 */}
      {currentVersionId && compareVersionId && (
        <VersionDiffDialog
          open={diffDialogOpen}
          onOpenChange={setDiffDialogOpen}
          modeName={modeName}
          taskName={taskName}
          agentName={agentName}
          baseVersionId={compareVersionId}
          compareVersionId={currentVersionId}
        />
      )}
    </>
  );
}
