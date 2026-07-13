import { Badge, Box, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import { formatDistanceToNow } from "date-fns";
import { enUS, zhCN } from "date-fns/locale";
import { Check, ChevronDown, ChevronLeft, GitCompare } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog } from "@/components";
import type { PromptChainVersion } from "@/lib/prompt-chain.types";

import "./version-history-sidebar.css";
import { VersionDiffDialog } from "./version-diff-dialog";

export interface VersionHistorySidebarProps {
  promptId: string;
  versions: PromptChainVersion[];
  currentVersion: PromptChainVersion | null;
  onCheckout: (versionId: string) => void;
  isCollapsed: boolean;
  onCollapsedChange: () => void;
}

function getDateLocale(language: string) {
  return language.startsWith("zh") ? zhCN : enUS;
}

export function VersionHistorySidebar({
  promptId,
  versions,
  currentVersion,
  onCheckout,
  isCollapsed,
  onCollapsedChange,
}: VersionHistorySidebarProps) {
  const { t, i18n } = useTranslation();
  const [compareVersionId, setCompareVersionId] = useState<string | null>(null);
  const [checkoutVersion, setCheckoutVersion] = useState<PromptChainVersion | null>(null);

  const currentVersionId = currentVersion?.id ?? null;

  return (
    <Box
      className="prompt-chain-version-history"
      data-slot="version-history-sidebar"
    >
      <button
        type="button"
        className="prompt-chain-version-history-header"
        aria-expanded={!isCollapsed}
        aria-label={
          isCollapsed
            ? t("promptChains.expandVersionHistory")
            : t("promptChains.collapseVersionHistory")
        }
        onClick={onCollapsedChange}
      >
        <Text
          size="1"
          weight="bold"
        >
          {t("promptChains.versionHistory")}
        </Text>
        <span
          className="prompt-chain-version-history-header-icon"
          aria-hidden="true"
        >
          {isCollapsed ? <ChevronLeft size={14} /> : <ChevronDown size={14} />}
        </span>
      </button>

      <div className="prompt-chain-version-history-content">
        {versions.length === 0 ? (
          <Flex
            className="prompt-chain-version-history-empty"
            align="center"
            justify="center"
          >
            <Text
              size="1"
              color="gray"
            >
              {t("promptChains.noVersions")}
            </Text>
          </Flex>
        ) : (
          <Box
            className="prompt-chain-version-history-list"
            aria-label={t("promptChains.versionHistory")}
            data-slot="version-history-list"
          >
            {versions.map((version) => {
              const isCurrent = version.id === currentVersionId;
              const canCompare = !!currentVersionId && !isCurrent;
              const isDefault = version.id === "default";
              const timeAgo = isDefault
                ? null
                : formatDistanceToNow(new Date(version.createdAt), {
                    addSuffix: true,
                    locale: getDateLocale(i18n.language),
                  });

              return (
                <Flex
                  key={version.id}
                  className="prompt-chain-version-history-row"
                  align="center"
                  data-current={isCurrent}
                  data-state={version.isActive ? "active" : "truncated"}
                  aria-current={isCurrent ? "true" : undefined}
                  title={version.note ?? undefined}
                >
                  <Box className="prompt-chain-version-history-tree-marker" />

                  <Flex
                    className="prompt-chain-version-history-details"
                    align="center"
                    gap="2"
                  >
                    <Text
                      className="prompt-chain-version-history-number"
                      size="1"
                      weight="medium"
                    >
                      v{version.versionNumber}
                    </Text>
                    {isDefault ? (
                      <Badge
                        className="prompt-chain-version-history-default"
                        color="gray"
                        size="1"
                      >
                        {t("promptChains.default")}
                      </Badge>
                    ) : (
                      <Text
                        className="prompt-chain-version-history-hash"
                        size="1"
                        color="gray"
                      >
                        {version.versionHash}
                      </Text>
                    )}
                    {isCurrent && (
                      <Badge
                        className="prompt-chain-version-history-current"
                        color="blue"
                        size="1"
                      >
                        {t("promptChains.currentVersion")}
                      </Badge>
                    )}
                    {!version.isActive && (
                      <Text
                        className="prompt-chain-version-history-truncated"
                        size="1"
                        color="orange"
                      >
                        {t("promptChains.truncated")}
                      </Text>
                    )}
                  </Flex>

                  {isCurrent && timeAgo ? (
                    <Text
                      className="prompt-chain-version-history-time"
                      size="1"
                      color="gray"
                    >
                      {timeAgo}
                    </Text>
                  ) : !isCurrent ? (
                    <Flex
                      className="prompt-chain-version-history-row-controls"
                      align="center"
                    >
                      {timeAgo && (
                        <Text
                          className="prompt-chain-version-history-time"
                          size="1"
                          color="gray"
                        >
                          {timeAgo}
                        </Text>
                      )}
                      <Flex
                        className="prompt-chain-version-history-actions"
                        align="center"
                        gap="1"
                      >
                        {canCompare && (
                          <Tooltip content={t("promptChains.diffWithCurrent")}>
                            <IconButton
                              variant="ghost"
                              size="1"
                              aria-label={t("promptChains.diffWithCurrent")}
                              onClick={() => setCompareVersionId(version.id)}
                            >
                              <GitCompare size={14} />
                            </IconButton>
                          </Tooltip>
                        )}
                        {!isDefault && (
                          <Tooltip content={t("promptChains.checkout")}>
                            <IconButton
                              variant="ghost"
                              size="1"
                              aria-label={t("promptChains.checkout")}
                              onClick={() => setCheckoutVersion(version)}
                            >
                              <Check size={14} />
                            </IconButton>
                          </Tooltip>
                        )}
                      </Flex>
                    </Flex>
                  ) : null}
                </Flex>
              );
            })}
          </Box>
        )}
      </div>

      {currentVersionId && compareVersionId && (
        <VersionDiffDialog
          open
          onOpenChange={(open) => !open && setCompareVersionId(null)}
          promptId={promptId}
          baseVersionId={compareVersionId}
          compareVersionId={currentVersionId}
        />
      )}

      <ConfirmDialog
        open={!!checkoutVersion}
        onOpenChange={(open) => !open && setCheckoutVersion(null)}
        onConfirm={() => {
          if (checkoutVersion) {
            onCheckout(checkoutVersion.id);
            setCheckoutVersion(null);
          }
        }}
        title={t("promptChains.checkoutConfirmTitle")}
        description={t("promptChains.checkoutConfirmDescription", {
          version: checkoutVersion?.versionNumber,
        })}
        confirmText={t("promptChains.checkout")}
        cancelText={t("promptChains.cancelButton")}
        confirmColor="blue"
      />
    </Box>
  );
}
