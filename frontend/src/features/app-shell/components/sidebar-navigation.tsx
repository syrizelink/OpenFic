import { Flex, Popover } from "@radix-ui/themes";
import { Ellipsis, Puzzle } from "lucide-react";
import { useLayoutEffect, useRef, useState, type ComponentProps, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useExtensionNavItems } from "@/features/plugins/use-extension-nav-items";

import {
  SIDEBAR_ICON_SIZE,
  SIDEBAR_ITEM_HEIGHT,
  type AppSidebarNavItem,
} from "./app-sidebar.constants";
import { RecentProjectsNav } from "./recent-projects-nav";
import { SidebarDivider, SidebarNav, SidebarNavItem } from "./sidebar-nav";

interface SidebarNavigationProps {
  items: AppSidebarNavItem[];
  isExpanded: boolean;
  recentProjects: Omit<
    ComponentProps<typeof RecentProjectsNav>,
    "isExpanded" | "atStart" | "onNavigate"
  >;
  onNavigate: () => void;
}

const SIDEBAR_DIVIDER_HEIGHT = 25;

export function SidebarNavigation({
  items,
  isExpanded,
  recentProjects,
  onNavigate,
}: SidebarNavigationProps) {
  const { t } = useTranslation();
  const extensionItems = useExtensionNavItems();
  const viewport = useRef<HTMLDivElement>(null);
  const [space, setSpace] = useState({ height: Infinity, gap: 4 });

  useLayoutEffect(() => {
    const node = viewport.current;
    if (!node) return;
    const measure = () => {
      const next = {
        height: node.getBoundingClientRect().height,
        gap: parseFloat(getComputedStyle(node).rowGap) || 0,
      };
      setSpace((previous) =>
        previous.height === next.height && previous.gap === next.gap ? previous : next,
      );
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const rows = [
    ...items.map((item) => ({ section: "main" as const, item })),
    ...recentProjects.projects.map((item) => ({ section: "recent" as const, item })),
    ...extensionItems.map((item) => ({ section: "extensions" as const, item })),
  ];
  let bottom = 0;
  let visibleCount = 0;
  let visibleCountWithMore = 0;
  let hasOverflow = false;
  for (const [index, row] of rows.entries()) {
    const previous = rows[index - 1];
    const gap = !previous
      ? 0
      : previous.section === row.section
        ? space.gap
        : row.section === "extensions"
          ? SIDEBAR_DIVIDER_HEIGHT
          : 2 * space.gap;
    bottom += gap + SIDEBAR_ITEM_HEIGHT;
    if (bottom <= space.height) visibleCount++;
    else if (row.section !== "recent") hasOverflow = true;
    if (bottom + space.gap + SIDEBAR_ITEM_HEIGHT <= space.height) visibleCountWithMore++;
  }
  if (hasOverflow) visibleCount = visibleCountWithMore;

  function renderEntries(entries: typeof rows, inPopover = false, close = onNavigate) {
    const expanded = inPopover || isExpanded;
    const main = entries.filter((row) => row.section === "main").map((row) => row.item);
    const projects = entries.filter((row) => row.section === "recent").map((row) => row.item);
    const extensions = entries.filter((row) => row.section === "extensions").map((row) => row.item);
    return (
      <>
        {main.length > 0 && (
          <SidebarNav
            items={main}
            isExpanded={expanded}
            onNavigate={close}
          />
        )}
        {!inPopover && (
          <RecentProjectsNav
            {...recentProjects}
            projects={projects}
            isExpanded={expanded}
            atStart={main.length === 0}
            onNavigate={close}
          />
        )}
        {extensions.length > 0 && (
          <>
            {main.length + projects.length > 0 && (
              <SidebarDivider
                isExpanded={expanded}
                inPopover={inPopover}
              />
            )}
            <Flex
              asChild
              direction="column"
              gap="1"
              width="100%"
            >
              <nav aria-label={t("plugins.region")}>
                {extensions.map(({ icon, ...item }) => (
                  <SidebarNavItem
                    key={item.href}
                    {...item}
                    icon={
                      <ExtensionIcon
                        key={icon}
                        src={icon}
                      />
                    }
                    isExpanded={expanded}
                    onNavigate={close}
                  />
                ))}
              </nav>
            </Flex>
          </>
        )}
      </>
    );
  }

  return (
    <div
      ref={viewport}
      className="app-sidebar-nav-viewport"
    >
      {renderEntries(rows.slice(0, visibleCount))}
      {hasOverflow && (
        <SidebarOverflow
          label={t("topbar.moreNavigation")}
          hasVisibleEntries={visibleCount > 0}
        >
          {(dismiss) =>
            renderEntries(
              rows.slice(visibleCount).filter((row) => row.section !== "recent"),
              true,
              () => {
                dismiss();
                onNavigate();
              },
            )
          }
        </SidebarOverflow>
      )}
    </div>
  );
}

function ExtensionIcon({ src }: { src?: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed)
    return (
      <Puzzle
        size={SIDEBAR_ICON_SIZE}
        aria-hidden="true"
      />
    );
  return (
    <img
      className="app-sidebar-extension-icon"
      src={src}
      alt=""
      width={SIDEBAR_ICON_SIZE}
      height={SIDEBAR_ICON_SIZE}
      onError={() => setFailed(true)}
    />
  );
}

function SidebarOverflow({
  label,
  hasVisibleEntries,
  children,
}: {
  label: string;
  hasVisibleEntries: boolean;
  children: (dismiss: () => void) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const openedOnHover = useRef(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const content = useRef<HTMLDivElement>(null);

  function cancelClose() {
    clearTimeout(closeTimer.current);
  }

  useLayoutEffect(() => () => clearTimeout(closeTimer.current), []);

  function scheduleClose() {
    cancelClose();
    if (!openedOnHover.current) return;
    closeTimer.current = setTimeout(() => {
      if (!content.current?.contains(document.activeElement)) setOpen(false);
    }, 180);
  }

  return (
    <Popover.Root
      open={open}
      onOpenChange={(next) => {
        cancelClose();
        if (next) openedOnHover.current = false;
        setOpen(next);
      }}
    >
      <Popover.Trigger>
        <button
          type="button"
          className="app-sidebar-nav-item app-sidebar-more-button"
          data-active={open || undefined}
          data-after-items={hasVisibleEntries || undefined}
          aria-label={label}
          onMouseDown={(event) => {
            if (open && openedOnHover.current) event.preventDefault();
          }}
          onPointerEnter={(event) => {
            if (event.pointerType !== "mouse") return;
            cancelClose();
            if (!open) {
              openedOnHover.current = true;
              setOpen(true);
            }
          }}
          onPointerLeave={scheduleClose}
          onClick={(event) => {
            if (open && openedOnHover.current) event.preventDefault();
          }}
        >
          <Ellipsis
            size={SIDEBAR_ICON_SIZE}
            aria-hidden="true"
          />
        </button>
      </Popover.Trigger>
      <Popover.Content
        ref={content}
        className="app-sidebar-overflow"
        aria-label={label}
        side="right"
        align="start"
        sideOffset={8}
        collisionPadding={8}
        size="1"
        onPointerEnter={cancelClose}
        onPointerLeave={scheduleClose}
        onOpenAutoFocus={(event) => {
          if (openedOnHover.current) event.preventDefault();
        }}
        onCloseAutoFocus={(event) => {
          if (openedOnHover.current) event.preventDefault();
        }}
      >
        {children(() => setOpen(false))}
      </Popover.Content>
    </Popover.Root>
  );
}
