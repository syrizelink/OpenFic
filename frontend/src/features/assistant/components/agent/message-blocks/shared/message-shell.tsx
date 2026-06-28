import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Box, Flex, IconButton } from "@radix-ui/themes";
import { ChevronDown } from "lucide-react";

import "./message-shell.css";
import { joinClassNames } from "./message-shell-utils";

interface MessageCardShellProps extends ComponentPropsWithoutRef<"div"> {
  children: ReactNode;
  cardTone?: "default" | "tool";
  expandable?: boolean;
  isStreaming?: boolean;
  status?: string;
}

interface MessageBlockShellProps extends MessageCardShellProps {
  flush?: boolean;
}

interface MessageBlockHeaderProps {
  children: ReactNode;
  className?: string;
  expandable?: boolean;
  expanded?: boolean;
  onToggle?: () => void;
}

interface MessageBlockContentProps {
  children: ReactNode;
  className?: string;
  contentClassName?: string;
  keepMounted?: boolean;
  marginTop?: number;
  motionKey: string;
  visible: boolean;
}

interface MessageExpandButtonProps {
  className?: string;
  expanded: boolean;
  label: string;
}

interface UserMessageShellProps {
  children: ReactNode;
  className?: string;
}

export function MessageCardShell({
  cardTone = "default",
  children,
  className,
  expandable,
  isStreaming,
  status,
  ...props
}: MessageCardShellProps) {
  return (
    <Box
      {...props}
      className={joinClassNames(
        "agent-message-card",
        "agent-message-card-shell",
        cardTone === "tool" && "agent-tool-card",
        className
      )}
      data-expandable={expandable === undefined ? undefined : expandable ? "true" : "false"}
      data-status={status}
      data-streaming={isStreaming === undefined ? undefined : isStreaming ? "true" : "false"}
    >
      {children}
    </Box>
  );
}

export function MessageBlockShell({
  cardTone = "tool",
  children,
  className,
  flush = false,
  ...props
}: MessageBlockShellProps) {
  return (
    <MessageCardShell
      {...props}
      cardTone={cardTone}
      className={joinClassNames(
        "agent-message-block-shell",
        flush && "agent-message-block-shell--flush",
        className
      )}
    >
      {children}
    </MessageCardShell>
  );
}

export function MessageBlockHeader({
  children,
  className,
  expandable = false,
  expanded,
  onToggle,
}: MessageBlockHeaderProps) {
  const isInteractive = expandable && typeof onToggle === "function";
  const handleToggle = () => {
    onToggle?.();
  };

  return (
    <Flex
      align="center"
      gap="2"
      justify="between"
      className={joinClassNames("agent-tool-header", "agent-message-shell-header", className)}
      data-expandable={expandable ? "true" : "false"}
      aria-expanded={expandable ? expanded : undefined}
      onClick={isInteractive ? handleToggle : undefined}
      onKeyDown={isInteractive ? (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        handleToggle();
      } : undefined}
      role={isInteractive ? "button" : undefined}
      tabIndex={isInteractive ? 0 : undefined}
    >
      {children}
    </Flex>
  );
}

export function MessageBlockHeaderMain({
  children,
  className,
}: ComponentPropsWithoutRef<typeof Flex>) {
  return (
    <Flex
      align="center"
      gap="2"
      className={joinClassNames("agent-tool-header-main", "agent-message-shell-header-main", className)}
    >
      {children}
    </Flex>
  );
}

export function MessageBlockMeta({
  children,
  className,
}: ComponentPropsWithoutRef<typeof Flex>) {
  return (
    <Flex
      align="center"
      gap="1"
      className={joinClassNames("agent-message-shell-meta", className)}
    >
      {children}
    </Flex>
  );
}

export function MessageExpandButton({
  className,
  expanded,
  label,
}: MessageExpandButtonProps) {
  return (
    <IconButton
      size="1"
      variant="ghost"
      className={joinClassNames(
        "agent-tool-expand-button",
        "agent-message-shell-expand-button",
        className
      )}
      tabIndex={-1}
      aria-label={label}
      data-expanded={expanded}
    >
      <ChevronDown size={14} />
    </IconButton>
  );
}

export function MessageBlockContent({
  children,
  className,
  contentClassName,
  keepMounted = false,
  marginTop = 8,
  motionKey,
  visible,
}: MessageBlockContentProps) {
  const contentShellClassName = joinClassNames("agent-tool-content-shell", className);
  const contentClassNames = joinClassNames("agent-tool-content", contentClassName);
  const collapsedState = { height: 0, opacity: 0, marginTop: 0 };
  const expandedState = { height: "auto", opacity: 1, marginTop };

  if (keepMounted) {
    return (
      <motion.div
        key={motionKey}
        className={contentShellClassName}
        initial={false}
        animate={visible ? expandedState : collapsedState}
        transition={{
          height: { duration: 0.2, ease: [0.22, 1, 0.36, 1] },
          opacity: { duration: 0.14, ease: "easeOut" },
          marginTop: { duration: 0.2, ease: [0.22, 1, 0.36, 1] },
        }}
        aria-hidden={!visible}
        inert={keepMounted && !visible ? true : undefined}
        style={keepMounted && !visible ? { pointerEvents: "none" } : undefined}
      >
        <Box className={contentClassNames}>{children}</Box>
      </motion.div>
    );
  }

  return (
    <AnimatePresence initial={false}>
      {visible ? (
        <motion.div
          key={motionKey}
          className={contentShellClassName}
          initial={collapsedState}
          animate={expandedState}
          exit={collapsedState}
          transition={{
            height: { duration: 0.2, ease: [0.22, 1, 0.36, 1] },
            opacity: { duration: 0.14, ease: "easeOut" },
            marginTop: { duration: 0.2, ease: [0.22, 1, 0.36, 1] },
          }}
          aria-hidden={!visible}
        >
          <Box className={contentClassNames}>{children}</Box>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export function UserMessageShell({ children, className }: UserMessageShellProps) {
  return (
    <Flex justify="end" className={joinClassNames("agent-message-user-shell-row", className)}>
      <Box className="agent-user-message-shell">{children}</Box>
    </Flex>
  );
}
