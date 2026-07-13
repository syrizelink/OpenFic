/**
 * VersionDiffDialog Component
 *
 * 版本差异对比弹窗 - GitHub 风格的并排 diff 视图
 */

import {
  Dialog,
  Flex,
  Text,
  Button,
  Box,
  ScrollArea,
  Badge,
  Separator,
  IconButton,
} from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import * as Diff from "diff";
import DiffMatchPatch from "diff-match-patch";
import {
  X,
  ArrowRight,
  FileDiff,
  FilePen,
  FileMinus,
  FilePlus,
  ChevronDown,
  ChevronRight,
  User,
  Bot,
  Terminal,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchPromptChainVersion } from "@/lib/api-client";
import type { PromptEntry } from "@/lib/prompt-chain.types";

interface VersionDiffDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  promptId: string;
  baseVersionId: string;
  compareVersionId: string;
}

interface EntryDiff {
  key: string;
  changeType: "added" | "deleted" | "modified";
  baseEntry: PromptEntry | null;
  compareEntry: PromptEntry | null;
}

interface LineDiff {
  oldLine: string | null;
  newLine: string | null;
  oldLineNum: number | null;
  newLineNum: number | null;
  type: "unchanged" | "added" | "deleted";
}

// 计算行级差异
function computeLineDiff(oldText: string, newText: string): LineDiff[] {
  const changes = Diff.diffLines(oldText, newText);
  const result: LineDiff[] = [];
  let oldLineNum = 1;
  let newLineNum = 1;

  changes.forEach((change) => {
    const lines = change.value.split("\n").filter(
      (line, idx, arr) => idx < arr.length - 1 || line !== "", // 移除最后的空行
    );

    if (change.added) {
      lines.forEach((line) => {
        result.push({
          oldLine: null,
          newLine: line,
          oldLineNum: null,
          newLineNum: newLineNum++,
          type: "added",
        });
      });
    } else if (change.removed) {
      lines.forEach((line) => {
        result.push({
          oldLine: line,
          newLine: null,
          oldLineNum: oldLineNum++,
          newLineNum: null,
          type: "deleted",
        });
      });
    } else {
      lines.forEach((line) => {
        result.push({
          oldLine: line,
          newLine: line,
          oldLineNum: oldLineNum++,
          newLineNum: newLineNum++,
          type: "unchanged",
        });
      });
    }
  });

  return result;
}

// 计算字符级差异
function computeInlineDiff(oldText: string, newText: string): Array<[number, string]> {
  const dmp = new DiffMatchPatch();
  const diffs = dmp.diff_main(oldText, newText);
  dmp.diff_cleanupSemantic(diffs);
  return diffs;
}

// 计算 token 数量（简单估算：按字符数 / 4）
function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

// 获取角色图标
function getRoleIcon(role: string) {
  switch (role.toLowerCase()) {
    case "user":
      return User;
    case "assistant":
      return Bot;
    case "system":
      return Terminal;
    default:
      return User;
  }
}

// 计算条目差异 - 使用 uid 进行匹配
function computeEntryDiffs(baseEntries: PromptEntry[], compareEntries: PromptEntry[]): EntryDiff[] {
  const result: EntryDiff[] = [];
  const baseMap = new Map(baseEntries.map((e) => [e.uid, e]));
  const compareMap = new Map(compareEntries.map((e) => [e.uid, e]));
  const processedUids = new Set<string>();

  // 处理所有条目
  const allUids = new Set([...baseMap.keys(), ...compareMap.keys()]);

  allUids.forEach((uid) => {
    if (processedUids.has(uid)) return;
    processedUids.add(uid);

    const baseEntry = baseMap.get(uid);
    const compareEntry = compareMap.get(uid);

    if (baseEntry && compareEntry) {
      // 两个版本都存在，检查是否有变化
      const hasChanges =
        baseEntry.role !== compareEntry.role ||
        baseEntry.content !== compareEntry.content ||
        baseEntry.isEnabled !== compareEntry.isEnabled ||
        baseEntry.name !== compareEntry.name ||
        baseEntry.orderIndex !== compareEntry.orderIndex;
      if (hasChanges) {
        result.push({
          key: uid,
          changeType: "modified",
          baseEntry,
          compareEntry,
        });
      }
    } else if (baseEntry && !compareEntry) {
      // 只在旧版本存在，说明被删除
      result.push({
        key: uid,
        changeType: "deleted",
        baseEntry,
        compareEntry: null,
      });
    } else if (!baseEntry && compareEntry) {
      // 只在新版本存在，说明是新增
      result.push({
        key: uid,
        changeType: "added",
        baseEntry: null,
        compareEntry,
      });
    }
  });

  // 按 orderIndex 排序
  return result.sort((a, b) => {
    const aIndex = (a.compareEntry || a.baseEntry)?.orderIndex || 0;
    const bIndex = (b.compareEntry || b.baseEntry)?.orderIndex || 0;
    return aIndex - bIndex;
  });
}

export function VersionDiffDialog({
  open,
  onOpenChange,
  promptId,
  baseVersionId,
  compareVersionId,
}: VersionDiffDialogProps) {
  const { t } = useTranslation();
  const [collapsedEntries, setCollapsedEntries] = useState<Set<string>>(new Set());

  // 获取两个版本的数据
  const {
    data: baseVersionData,
    isLoading: isLoadingBase,
    error: errorBase,
  } = useQuery({
    queryKey: ["promptChainVersion", promptId, baseVersionId],
    queryFn: () => fetchPromptChainVersion(promptId, baseVersionId),
    enabled: open && !!baseVersionId,
  });

  const {
    data: compareVersionData,
    isLoading: isLoadingCompare,
    error: errorCompare,
  } = useQuery({
    queryKey: ["promptChainVersion", promptId, compareVersionId],
    queryFn: () => fetchPromptChainVersion(promptId, compareVersionId),
    enabled: open && !!compareVersionId,
  });

  const isLoading = isLoadingBase || isLoadingCompare;
  const error = errorBase || errorCompare;
  const diffs =
    baseVersionData && compareVersionData
      ? computeEntryDiffs(baseVersionData.entries, compareVersionData.entries)
      : [];

  // 切换折叠状态
  const toggleCollapse = (key: string) => {
    setCollapsedEntries((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // 渲染带字符级高亮的文本（用于旧版本，只显示删除的部分）
  const renderInlineDiffOld = (diffs: Array<[number, string]>) => (
    <span>
      {diffs.map((diff, idx) => {
        const [op, value] = diff;
        if (op === -1)
          return (
            <span
              key={idx}
              style={{
                background: "var(--red-a5)",
                color: "var(--red-12)",
                textDecoration: "line-through",
              }}
            >
              {value}
            </span>
          );
        if (op === 0) return <span key={idx}>{value}</span>;
        return null; // 不显示新增的部分
      })}
    </span>
  );

  // 渲染带字符级高亮的文本（用于新版本，只显示新增的部分）
  const renderInlineDiffNew = (diffs: Array<[number, string]>) => (
    <span>
      {diffs.map((diff, idx) => {
        const [op, value] = diff;
        if (op === 1)
          return (
            <span
              key={idx}
              style={{ background: "var(--green-a5)", color: "var(--green-12)" }}
            >
              {value}
            </span>
          );
        if (op === 0) return <span key={idx}>{value}</span>;
        return null; // 不显示删除的部分
      })}
    </span>
  );

  // 渲染单行
  const renderLine = (
    lineNum: number | null,
    content: string | null,
    type: "old" | "new",
    diffType: LineDiff["type"],
    inlineDiffs?: Array<[number, string]>,
  ) => {
    const isVisible =
      (diffType === "added" && type === "new") ||
      (diffType === "deleted" && type === "old") ||
      diffType === "unchanged";
    const bgColor =
      diffType === "added" && type === "new"
        ? "var(--green-a3)"
        : diffType === "deleted" && type === "old"
          ? "var(--red-a3)"
          : "transparent";
    const lineNumBg =
      diffType === "added" && type === "new"
        ? "var(--green-a4)"
        : diffType === "deleted" && type === "old"
          ? "var(--red-a4)"
          : "var(--gray-a2)";

    return (
      <Flex
        style={{
          background: isVisible ? bgColor : "var(--gray-a2)",
          minHeight: "20px",
          fontSize: "12px",
          fontFamily: "var(--code-font-family, monospace)",
        }}
      >
        <Box
          style={{
            width: "50px",
            flexShrink: 0,
            textAlign: "right",
            paddingRight: "8px",
            paddingLeft: "4px",
            background: isVisible ? lineNumBg : "var(--gray-a3)",
            color: "var(--gray-11)",
            userSelect: "none",
            borderRight: "1px solid var(--gray-a5)",
          }}
        >
          {isVisible && lineNum !== null ? lineNum : ""}
        </Box>
        <Box
          style={{
            flex: 1,
            paddingLeft: "8px",
            paddingRight: "8px",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            overflowWrap: "break-word",
          }}
        >
          {isVisible && content !== null
            ? inlineDiffs
              ? type === "old"
                ? renderInlineDiffOld(inlineDiffs)
                : renderInlineDiffNew(inlineDiffs)
              : content
            : ""}
        </Box>
      </Flex>
    );
  };

  // 渲染条目差异
  const renderEntryDiff = (diff: EntryDiff) => {
    const { baseEntry, compareEntry, changeType, key } = diff;

    // 检查是否只有名称/角色变化（内容没变）
    const onlyMetadataChanged =
      changeType === "modified" &&
      baseEntry &&
      compareEntry &&
      baseEntry.content === compareEntry.content &&
      (baseEntry.name !== compareEntry.name || baseEntry.role !== compareEntry.role);

    // 如果只有元数据变化，默认折叠且不可展开
    const isCollapsed = onlyMetadataChanged ? true : collapsedEntries.has(key);
    const canToggle = !onlyMetadataChanged;

    // 获取变更图标和颜色
    const getChangeIcon = () => {
      switch (changeType) {
        case "added":
          return FilePlus;
        case "deleted":
          return FileMinus;
        case "modified":
          return FilePen;
      }
    };
    const ChangeIcon = getChangeIcon();
    const iconColor =
      changeType === "added"
        ? "var(--green-9)"
        : changeType === "deleted"
          ? "var(--red-9)"
          : "var(--amber-9)";

    // 获取角色信息
    const baseRole = baseEntry?.role || "user";
    const compareRole = compareEntry?.role || "user";
    const BaseRoleIcon = getRoleIcon(baseRole);
    const CompareRoleIcon = getRoleIcon(compareRole);

    // 计算行数变化和 token 变化
    let addedLines = 0;
    let deletedLines = 0;
    let baseTokens = 0;
    let compareTokens = 0;

    if (changeType === "added" && compareEntry) {
      addedLines = compareEntry.content.split("\n").length;
      compareTokens = estimateTokens(compareEntry.content);
    } else if (changeType === "deleted" && baseEntry) {
      deletedLines = baseEntry.content.split("\n").length;
      baseTokens = estimateTokens(baseEntry.content);
    } else if (changeType === "modified" && baseEntry && compareEntry) {
      const lineDiffs = computeLineDiff(baseEntry.content, compareEntry.content);
      addedLines = lineDiffs.filter((ld) => ld.type === "added").length;
      deletedLines = lineDiffs.filter((ld) => ld.type === "deleted").length;
      baseTokens = estimateTokens(baseEntry.content);
      compareTokens = estimateTokens(compareEntry.content);
    }

    const renderHeader = () => (
      <Flex
        align="center"
        gap="2"
        p="2"
        style={{
          background: "var(--gray-a2)",
          borderBottom: isCollapsed ? "none" : "1px solid var(--gray-a5)",
          cursor: canToggle ? "pointer" : "default",
          userSelect: "none",
        }}
        onClick={() => canToggle && toggleCollapse(key)}
      >
        {/* 左侧：折叠按钮 + 变更类型图标 + 名称 + 角色图标 */}
        <Flex
          align="center"
          gap="2"
          style={{ flex: 1 }}
        >
          {canToggle ? (
            <IconButton
              size="1"
              variant="ghost"
              style={{ cursor: "pointer" }}
            >
              {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
            </IconButton>
          ) : (
            <Box style={{ width: "24px" }} /> // 占位，保持对齐
          )}
          <ChangeIcon
            size={16}
            style={{ color: iconColor }}
          />

          {/* 条目名称和角色的变化显示 */}
          {changeType === "modified" &&
          baseEntry &&
          compareEntry &&
          (baseEntry.name !== compareEntry.name || baseEntry.role !== compareEntry.role) ? (
            <>
              <Text
                size="2"
                weight="bold"
              >
                {baseEntry.name}
              </Text>
              <BaseRoleIcon
                size={16}
                style={{ color: "var(--gray-10)" }}
              />
              <ArrowRight size={14} />
              <Text
                size="2"
                weight="bold"
              >
                {compareEntry.name}
              </Text>
              <CompareRoleIcon
                size={16}
                style={{ color: "var(--gray-10)" }}
              />
            </>
          ) : (
            <>
              <Text
                size="2"
                weight="bold"
              >
                {baseEntry?.name || compareEntry?.name}
              </Text>
              <CompareRoleIcon
                size={16}
                style={{ color: "var(--gray-10)" }}
              />
            </>
          )}
        </Flex>

        {/* 右侧：统计信息 */}
        <Flex
          align="center"
          gap="2"
        >
          {/* 行数变化 */}
          {(addedLines > 0 || deletedLines > 0) && (
            <Flex
              align="center"
              gap="1"
            >
              {deletedLines > 0 && (
                <Text
                  size="1"
                  style={{
                    color: "var(--red-9)",
                    fontFamily: "var(--code-font-family, monospace)",
                  }}
                >
                  -{deletedLines}
                </Text>
              )}
              {addedLines > 0 && (
                <Text
                  size="1"
                  style={{
                    color: "var(--green-9)",
                    fontFamily: "var(--code-font-family, monospace)",
                  }}
                >
                  +{addedLines}
                </Text>
              )}
            </Flex>
          )}

          {/* 分隔线 */}
          {(addedLines > 0 || deletedLines > 0) && (baseTokens > 0 || compareTokens > 0) && (
            <Separator
              orientation="vertical"
              style={{ height: "16px" }}
            />
          )}

          {/* Token 变化 */}
          {changeType === "modified" && baseTokens > 0 && compareTokens > 0 && (
            <Flex
              align="center"
              gap="1"
            >
              <Text
                size="1"
                color="gray"
                style={{ fontFamily: "var(--code-font-family, monospace)" }}
              >
                {baseTokens} → {compareTokens}
              </Text>
              {compareTokens !== baseTokens && (
                <Text
                  size="1"
                  style={{
                    color: compareTokens > baseTokens ? "var(--green-9)" : "var(--red-9)",
                    fontFamily: "var(--code-font-family, monospace)",
                  }}
                >
                  ({compareTokens > baseTokens ? "+" : ""}
                  {compareTokens - baseTokens})
                </Text>
              )}
            </Flex>
          )}
          {changeType === "added" && compareTokens > 0 && (
            <Text
              size="1"
              color="gray"
              style={{ fontFamily: "var(--code-font-family, monospace)" }}
            >
              {compareTokens} tokens
            </Text>
          )}
          {changeType === "deleted" && baseTokens > 0 && (
            <Text
              size="1"
              color="gray"
              style={{ fontFamily: "var(--code-font-family, monospace)" }}
            >
              {baseTokens} tokens
            </Text>
          )}
        </Flex>
      </Flex>
    );

    const containerStyle = {
      border: "1px solid var(--gray-a5)",
      borderRadius: "var(--radius-2)",
      overflow: "hidden",
      marginBottom: "16px",
    };

    // 新增条目
    if (changeType === "added" && compareEntry) {
      const lines = compareEntry.content.split("\n");
      return (
        <Box style={containerStyle}>
          {renderHeader()}
          <AnimatePresence initial={false}>
            {!isCollapsed && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2, ease: "easeInOut" }}
                style={{ overflow: "hidden" }}
              >
                <Flex>
                  <Box style={{ flex: 1, background: "var(--gray-a2)", minWidth: 0 }}>
                    {lines.map((_, idx) => (
                      <Box key={`e-${idx}`}>{renderLine(null, null, "old", "added")}</Box>
                    ))}
                  </Box>
                  <Box style={{ flex: 1, minWidth: 0 }}>
                    {lines.map((line, idx) => (
                      <Box key={`n-${idx}`}>{renderLine(idx + 1, line, "new", "added")}</Box>
                    ))}
                  </Box>
                </Flex>
              </motion.div>
            )}
          </AnimatePresence>
        </Box>
      );
    }

    // 删除条目
    if (changeType === "deleted" && baseEntry) {
      const lines = baseEntry.content.split("\n");
      return (
        <Box style={containerStyle}>
          {renderHeader()}
          <AnimatePresence initial={false}>
            {!isCollapsed && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2, ease: "easeInOut" }}
                style={{ overflow: "hidden" }}
              >
                <Flex>
                  <Box style={{ flex: 1, minWidth: 0 }}>
                    {lines.map((line, idx) => (
                      <Box key={`o-${idx}`}>{renderLine(idx + 1, line, "old", "deleted")}</Box>
                    ))}
                  </Box>
                  <Box style={{ flex: 1, background: "var(--gray-a2)", minWidth: 0 }}>
                    {lines.map((_, idx) => (
                      <Box key={`e-${idx}`}>{renderLine(null, null, "new", "deleted")}</Box>
                    ))}
                  </Box>
                </Flex>
              </motion.div>
            )}
          </AnimatePresence>
        </Box>
      );
    }

    // 修改条目
    if (changeType === "modified" && baseEntry && compareEntry) {
      // baseEntry 是旧版本，compareEntry 是新版本
      const lineDiffs = computeLineDiff(baseEntry.content, compareEntry.content);

      return (
        <Box style={containerStyle}>
          {renderHeader()}
          <AnimatePresence initial={false}>
            {!isCollapsed && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2, ease: "easeInOut" }}
                style={{ overflow: "hidden" }}
              >
                <Flex>
                  {/* 左侧：旧版本（baseEntry） - 只显示删除的字符 */}
                  <Box style={{ flex: 1, borderRight: "1px solid var(--gray-a5)", minWidth: 0 }}>
                    {lineDiffs.map((ld, idx) => {
                      // 对于 unchanged 行，不需要字符级 diff
                      if (ld.type === "unchanged") {
                        return (
                          <Box key={`o-${idx}`}>
                            {renderLine(ld.oldLineNum, ld.oldLine, "old", ld.type)}
                          </Box>
                        );
                      }

                      // 对于 deleted 行，尝试找到对应的 added 行进行字符级对比
                      let inlineDiffs: Array<[number, string]> | undefined;
                      if (ld.type === "deleted" && ld.oldLine) {
                        const nextAdded = lineDiffs.find((d, i) => i > idx && d.type === "added");
                        if (nextAdded?.newLine) {
                          inlineDiffs = computeInlineDiff(ld.oldLine, nextAdded.newLine);
                        }
                      }

                      return (
                        <Box key={`o-${idx}`}>
                          {renderLine(ld.oldLineNum, ld.oldLine, "old", ld.type, inlineDiffs)}
                        </Box>
                      );
                    })}
                  </Box>
                  {/* 右侧：新版本（compareEntry） - 只显示新增的字符 */}
                  <Box style={{ flex: 1, minWidth: 0 }}>
                    {lineDiffs.map((ld, idx) => {
                      // 对于 unchanged 行，不需要字符级 diff
                      if (ld.type === "unchanged") {
                        return (
                          <Box key={`n-${idx}`}>
                            {renderLine(ld.newLineNum, ld.newLine, "new", ld.type)}
                          </Box>
                        );
                      }

                      // 对于 added 行，尝试找到对应的 deleted 行进行字符级对比
                      let inlineDiffs: Array<[number, string]> | undefined;
                      if (ld.type === "added" && ld.newLine) {
                        const prevDeleted = lineDiffs
                          .slice(0, idx)
                          .reverse()
                          .find((d) => d.type === "deleted");
                        if (prevDeleted?.oldLine) {
                          inlineDiffs = computeInlineDiff(prevDeleted.oldLine, ld.newLine);
                        }
                      }

                      return (
                        <Box key={`n-${idx}`}>
                          {renderLine(ld.newLineNum, ld.newLine, "new", ld.type, inlineDiffs)}
                        </Box>
                      );
                    })}
                  </Box>
                </Flex>
              </motion.div>
            )}
          </AnimatePresence>
        </Box>
      );
    }

    return null;
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={onOpenChange}
    >
      <Dialog.Content style={{ maxWidth: "1200px", maxHeight: "90vh" }}>
        <Flex
          justify="between"
          align="center"
          mb="3"
        >
          <Flex
            align="center"
            gap="2"
            style={{ alignItems: "center" }}
          >
            <FileDiff
              size={20}
              style={{ color: "var(--gray-11)", flexShrink: 0 }}
            />
            <Dialog.Title style={{ margin: 0 }}>{t("promptChains.versionDiff")}</Dialog.Title>
          </Flex>
          <Dialog.Close>
            <Button
              variant="ghost"
              size="1"
            >
              <X size={16} />
            </Button>
          </Dialog.Close>
        </Flex>

        {isLoading && (
          <Flex
            align="center"
            justify="center"
            py="9"
          >
            <Text
              size="2"
              color="gray"
            >
              {t("common.loading")}
            </Text>
          </Flex>
        )}

        {error && (
          <Flex
            align="center"
            justify="center"
            py="9"
          >
            <Text
              size="2"
              color="red"
            >
              {t("promptChains.diffLoadFailed")}
            </Text>
          </Flex>
        )}

        {baseVersionData && compareVersionData && (
          <>
            <Flex
              align="center"
              gap="2"
              mb="4"
            >
              <Badge color="blue">v{baseVersionData.version.versionNumber}</Badge>
              <ArrowRight size={14} />
              <Badge color="blue">v{compareVersionData.version.versionNumber}</Badge>
              <Separator orientation="vertical" />
              <Text
                size="1"
                color="gray"
              >
                {diffs.length === 0
                  ? t("promptChains.noDifferences")
                  : t("promptChains.differencesCount", { count: diffs.length })}
              </Text>
            </Flex>

            <ScrollArea style={{ maxHeight: "calc(90vh - 180px)" }}>
              <Flex
                direction="column"
                gap="3"
              >
                {diffs.length === 0 ? (
                  <Box
                    p="6"
                    style={{
                      textAlign: "center",
                      color: "var(--gray-a9)",
                      border: "1px dashed var(--gray-a5)",
                      borderRadius: "var(--radius-2)",
                    }}
                  >
                    <Text size="2">{t("promptChains.versionsIdentical")}</Text>
                  </Box>
                ) : (
                  diffs.map((diff) => <Box key={diff.key}>{renderEntryDiff(diff)}</Box>)
                )}
              </Flex>
            </ScrollArea>
          </>
        )}

        <Flex
          gap="3"
          mt="4"
          justify="end"
        >
          <Dialog.Close>
            <Button
              variant="soft"
              color="gray"
            >
              {t("promptChains.close")}
            </Button>
          </Dialog.Close>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
