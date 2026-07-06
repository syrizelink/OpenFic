import { Box, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import {
  AtSign,
  AlignLeft,
  ArrowDown,
  ArrowUp,
  ChevronRight,
  FilePlus,
  MoreHorizontal,
  Pencil,
  Trash2,
} from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useMemo, useState, type MouseEvent } from "react";
import { useTranslation } from "react-i18next";

import { ContextMenu, type ContextMenuItem } from "@/components";
import { buildVolumeMentionTag } from "@/features/assistant/lib/mention-text";
import type { VolumeWithChapters } from "@/lib/chapter.types";

const MotionBox = motion.create(Box);

const VOLUME_HEADER_TRANSITION = {
  duration: 0.2,
  ease: [0.22, 1, 0.36, 1],
} as const;

function HeaderRenameInput({
  initialValue,
  onConfirm,
  onCancel,
}: {
  initialValue: string;
  onConfirm: (value: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initialValue);

  const submit = useCallback(() => {
    const nextValue = value.trim();
    if (nextValue && nextValue !== initialValue) {
      onConfirm(nextValue);
      return;
    }
    onCancel();
  }, [initialValue, onCancel, onConfirm, value]);

  return (
    <input
      autoFocus
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onBlur={submit}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          submit();
        }
        if (event.key === "Escape") {
          event.preventDefault();
          onCancel();
        }
      }}
      onClick={(event) => event.stopPropagation()}
      style={{
        width: "100%",
        height: 22,
        border: "none",
        outline: "none",
        background: "transparent",
        color: "var(--gray-12)",
        fontFamily: "inherit",
        fontSize: 14,
        fontWeight: 600,
      }}
    />
  );
}

interface VolumeHeaderProps {
  volume: VolumeWithChapters;
  isExpanded: boolean;
  isRenaming: boolean;
  isFirst: boolean;
  isLast: boolean;
  canDelete?: boolean;
  isAgentLocked?: boolean;
  onToggle: () => void;
  onStartRename: () => void;
  onRenameConfirm: (title: string) => void;
  onRenameCancel: () => void;
  onEditDescription: () => void;
  onCreateChapter: () => void;
  onAddToConversation?: (markup: string) => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDelete: () => void;
  onLockedAction?: () => void;
}

export function VolumeHeader({
  volume,
  isExpanded,
  isRenaming,
  isFirst,
  isLast,
  canDelete = true,
  isAgentLocked = false,
  onToggle,
  onStartRename,
  onRenameConfirm,
  onRenameCancel,
  onEditDescription,
  onCreateChapter,
  onAddToConversation,
  onMoveUp,
  onMoveDown,
  onDelete,
  onLockedAction,
}: VolumeHeaderProps) {
  const { t } = useTranslation();
  const [contextMenuPos, setContextMenuPos] = useState<{ x: number; y: number } | null>(null);

  const openMenu = useCallback(
    (position: { x: number; y: number }) => {
      if (isAgentLocked) {
        onLockedAction?.();
        return;
      }
      setContextMenuPos(position);
    },
    [isAgentLocked, onLockedAction],
  );

  const menuItems = useMemo<ContextMenuItem[]>(() => {
    const items: ContextMenuItem[] = [
      {
        id: "rename",
        label: t("volume.menu.rename"),
        icon: Pencil,
        onClick: onStartRename,
      },
      {
        id: "editDescription",
        label: t("volume.menu.editDescription"),
        icon: AlignLeft,
        onClick: onEditDescription,
      },
      {
        id: "newChapter",
        label: t("volume.menu.newChapter"),
        icon: FilePlus,
        onClick: onCreateChapter,
      },
      {
        id: "addToConversation",
        label: t("volume.menu.addToConversation"),
        icon: AtSign,
        disabled: !onAddToConversation,
        onClick: () =>
          onAddToConversation?.(
            buildVolumeMentionTag({
              volumeId: volume.id,
              label: volume.title.trim() || t("volume.untitled"),
            }),
          ),
      },
      {
        id: "moveUp",
        label: t("volume.menu.moveUp"),
        icon: ArrowUp,
        disabled: isFirst,
        onClick: onMoveUp,
      },
      {
        id: "moveDown",
        label: t("volume.menu.moveDown"),
        icon: ArrowDown,
        disabled: isLast,
        onClick: onMoveDown,
      },
    ];

    if (canDelete) {
      items.push({
        id: "delete",
        label: t("volume.menu.delete"),
        icon: Trash2,
        danger: true,
        onClick: onDelete,
      });
    }

    return items;
  }, [
    canDelete,
    isFirst,
    isLast,
    onCreateChapter,
    onAddToConversation,
    onDelete,
    onEditDescription,
    onMoveDown,
    onMoveUp,
    onStartRename,
    volume.id,
    volume.title,
    t,
  ]);

  return (
    <>
      <MotionBox
        initial={false}
        onContextMenu={(event: MouseEvent<HTMLDivElement>) => {
          event.preventDefault();
          openMenu({ x: event.clientX, y: event.clientY });
        }}
        transition={VOLUME_HEADER_TRANSITION}
        style={{
          borderTop: "1px solid var(--gray-a4)",
          background: "var(--gray-2)",
          overflow: "hidden",
          position: "relative",
        }}
      >
        <motion.div
          initial={false}
          aria-hidden="true"
          animate={{ opacity: isExpanded ? 1 : 0 }}
          transition={VOLUME_HEADER_TRANSITION}
          style={{
            position: "absolute",
            inset: 0,
            background: "var(--gray-a2)",
            pointerEvents: "none",
          }}
        />
        <motion.div
          initial={false}
          aria-hidden="true"
          animate={{
            opacity: isExpanded ? 1 : 0,
            scaleX: isExpanded ? 1 : 0.96,
          }}
          transition={VOLUME_HEADER_TRANSITION}
          style={{
            position: "absolute",
            right: 0,
            bottom: 0,
            left: 0,
            height: 1,
            background: "var(--gray-a3)",
            transformOrigin: "left center",
            pointerEvents: "none",
          }}
        />
        <Flex
          align="center"
          gap="2"
          px="3"
          py="2"
          style={{ minWidth: 0 }}
        >
          <IconButton
            variant="ghost"
            color="gray"
            size="1"
            onClick={onToggle}
            aria-label={isExpanded ? t("common.collapse") : t("common.expand")}
          >
            <motion.div
              initial={false}
              animate={{ rotate: isExpanded ? 90 : 0 }}
              transition={VOLUME_HEADER_TRANSITION}
              style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
            >
              <ChevronRight size={15} />
            </motion.div>
          </IconButton>

          <Box
            style={{ flex: 1, minWidth: 0 }}
            onClick={onToggle}
          >
            {isRenaming ? (
              <HeaderRenameInput
                initialValue={volume.title}
                onConfirm={onRenameConfirm}
                onCancel={onRenameCancel}
              />
            ) : (
              <Text
                size="2"
                weight="bold"
                style={{
                  display: "block",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  color: "var(--gray-12)",
                  cursor: "pointer",
                }}
              >
                {volume.title || t("volume.untitled")}
              </Text>
            )}
            {volume.description ? (
              <Text
                size="1"
                color="gray"
                style={{
                  display: "block",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {volume.description}
              </Text>
            ) : null}
          </Box>

          <Text
            size="1"
            color="gray"
            style={{ flexShrink: 0 }}
          >
            {volume.chapterCount}
          </Text>

          <Tooltip content={t("volume.menu.moreActions")}>
            <IconButton
              variant="ghost"
              color="gray"
              size="1"
              onClick={(event) => {
                event.stopPropagation();
                const rect = event.currentTarget.getBoundingClientRect();
                openMenu({ x: rect.left, y: rect.bottom + 4 });
              }}
              aria-label={t("volume.menu.moreActions")}
            >
              <MoreHorizontal size={15} />
            </IconButton>
          </Tooltip>
        </Flex>
      </MotionBox>

      <ContextMenu
        position={contextMenuPos}
        items={menuItems}
        onClose={() => setContextMenuPos(null)}
      />
    </>
  );
}
