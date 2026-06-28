/**
 * ProjectsToolbar Component
 *
 * 项目列表工具栏，包含创建、导入、搜索、排序、视图切换功能。
 */

import type { ReactNode } from "react";
import {
  Box,
  Button,
  Flex,
  TextField,
  DropdownMenu,
  Tooltip,
  SegmentedControl,
  IconButton,
} from "@radix-ui/themes";
import {
  Plus,
  Upload,
  Search,
  ArrowUpDown,
  LayoutGrid,
  List,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  useProjectsStore,
  type ViewMode,
  type SortBy,
} from "../store/use-projects-store";

interface ProjectsToolbarProps {
  leadingSlot?: ReactNode;
  onCreateClick: () => void;
  onImportClick: () => void;
}

export function ProjectsToolbar({
  leadingSlot,
  onCreateClick,
  onImportClick,
}: ProjectsToolbarProps) {
  const { t } = useTranslation();

  const {
    viewMode,
    setViewMode,
    searchQuery,
    setSearchQuery,
    sortBy,
    setSortBy,
  } = useProjectsStore();

  const sortOptions: { value: SortBy; label: string }[] = [
    { value: "updated_at", label: t("projects.sortByUpdated") },
    { value: "created_at", label: t("projects.sortByCreated") },
    { value: "title", label: t("projects.sortByTitle") },
  ];

  const currentSortLabel =
    sortOptions.find((opt) => opt.value === sortBy)?.label ??
    t("projects.sort");

  // 当前视图图标
  const CurrentViewIcon = viewMode === "grid" ? LayoutGrid : List;

  return (
    <Box py="4">
      {/* 桌面端布局：单行 */}
      <Flex
        display={{ initial: "none", sm: "flex" }}
        justify="between"
        align="center"
        gap="4"
      >
        {/* 左侧：创建、导入 */}
        <Flex gap="2">
          <Button size="2" onClick={onCreateClick}>
            <Plus size={16} />
            {t("projects.newProject")}
          </Button>
          <Button size="2" variant="soft" onClick={onImportClick}>
            <Upload size={16} />
            {t("projects.import")}
          </Button>
        </Flex>

        {/* 右侧：搜索、排序、视图切换 */}
        <Flex gap="3" align="center">
          {/* 搜索 */}
          <TextField.Root
            placeholder={t("projects.searchPlaceholder")}
            size="2"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: "200px" }}
          >
            <TextField.Slot>
              <Search size={14} />
            </TextField.Slot>
          </TextField.Root>

          {/* 排序 */}
          <DropdownMenu.Root>
            <DropdownMenu.Trigger>
              <Button variant="soft" size="2" style={{ padding: "0 8px" }}>
                <Flex align="center">
                  <ArrowUpDown size={14} style={{ flexShrink: 0 }} />
                  <Box
                    style={{
                      width: "6.5em",
                      textAlign: "center",
                      flexShrink: 0,
                    }}
                  >
                    {currentSortLabel}
                  </Box>
                </Flex>
              </Button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Content>
              {sortOptions.map((option) => (
                <DropdownMenu.Item
                  key={option.value}
                  onSelect={() => setSortBy(option.value)}
                >
                  {option.label}
                </DropdownMenu.Item>
              ))}
            </DropdownMenu.Content>
          </DropdownMenu.Root>

          {/* 视图切换 */}
          <SegmentedControl.Root
            value={viewMode}
            onValueChange={(value) => setViewMode(value as ViewMode)}
            size="1"
          >
            <SegmentedControl.Item value="grid">
              <Tooltip content={t("projects.gridView")}>
                <Flex
                  align="center"
                  justify="center"
                  width="24px"
                  height="24px"
                >
                  <LayoutGrid size={14} />
                </Flex>
              </Tooltip>
            </SegmentedControl.Item>
            <SegmentedControl.Item value="list">
              <Tooltip content={t("projects.listView")}>
                <Flex
                  align="center"
                  justify="center"
                  width="24px"
                  height="24px"
                >
                  <List size={14} />
                </Flex>
              </Tooltip>
            </SegmentedControl.Item>
          </SegmentedControl.Root>
        </Flex>
      </Flex>

      {/* 移动端布局：两行 */}
      <Flex
        display={{ initial: "flex", sm: "none" }}
        direction="column"
        gap="3"
      >
        <Flex align="center" gap="2" wrap="wrap">
          {leadingSlot}

          <Flex gap="1">
            <Tooltip content={t("projects.newProject")}>
              <IconButton
                variant="ghost"
                size="2"
                aria-label={t("projects.newProject")}
                onClick={onCreateClick}
              >
                <Plus size={16} />
              </IconButton>
            </Tooltip>
            <Tooltip content={t("projects.import")}>
              <IconButton
                variant="ghost"
                size="2"
                aria-label={t("projects.import")}
                onClick={onImportClick}
              >
                <Upload size={16} />
              </IconButton>
            </Tooltip>
          </Flex>
        </Flex>

        <Flex align="center" gap="2">
          <TextField.Root
            placeholder={t("projects.searchPlaceholder")}
            size="2"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: "100%", flex: 1 }}
          >
            <TextField.Slot>
              <Search size={14} />
            </TextField.Slot>
          </TextField.Root>

          <Tooltip content={currentSortLabel}>
            <DropdownMenu.Root>
              <DropdownMenu.Trigger>
                <IconButton variant="ghost" size="2" aria-label={currentSortLabel}>
                  <ArrowUpDown size={14} />
                </IconButton>
              </DropdownMenu.Trigger>
              <DropdownMenu.Content>
                {sortOptions.map((option) => (
                  <DropdownMenu.Item
                    key={option.value}
                    onSelect={() => setSortBy(option.value)}
                  >
                    {option.label}
                  </DropdownMenu.Item>
                ))}
              </DropdownMenu.Content>
            </DropdownMenu.Root>
          </Tooltip>

          <Tooltip
            content={
              viewMode === "grid"
                ? t("projects.switchToListView")
                : t("projects.switchToGridView")
            }
          >
            <IconButton
              variant="ghost"
              size="2"
              onClick={() =>
                setViewMode(viewMode === "grid" ? "list" : "grid")
              }
            >
              <CurrentViewIcon size={14} />
            </IconButton>
          </Tooltip>
        </Flex>
      </Flex>
    </Box>
  );
}
