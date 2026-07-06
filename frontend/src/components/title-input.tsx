import { Box } from "@radix-ui/themes";
import { useCallback, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

const MOBILE_TITLE_LONG_PRESS_MS = 280;
const MOBILE_TITLE_MOVE_TOLERANCE = 8;

export interface TitleInputProps {
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  disabled?: boolean;
  onDisabledClick?: () => void;
  placeholder?: string;
}

export function TitleInput({
  value,
  onChange,
  onBlur,
  disabled = false,
  onDisabledClick,
  placeholder,
}: TitleInputProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const longPressTimerRef = useRef<number | null>(null);
  const pointerRef = useRef<{
    pointerId: number;
    x: number;
    y: number;
    isLongPress: boolean;
  } | null>(null);

  const clearLongPress = useCallback(() => {
    if (longPressTimerRef.current !== null) {
      window.clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  }, []);

  const clearPointer = useCallback(() => {
    clearLongPress();
    pointerRef.current = null;
  }, [clearLongPress]);

  useEffect(() => clearPointer, [clearPointer]);

  const handlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLInputElement>) => {
      if (event.pointerType === "mouse" || event.button !== 0 || disabled) return;

      clearPointer();
      pointerRef.current = {
        pointerId: event.pointerId,
        x: event.clientX,
        y: event.clientY,
        isLongPress: false,
      };

      longPressTimerRef.current = window.setTimeout(() => {
        if (!pointerRef.current) return;
        pointerRef.current.isLongPress = true;
        inputRef.current?.blur();
      }, MOBILE_TITLE_LONG_PRESS_MS);
    },
    [clearPointer, disabled],
  );

  const handlePointerMove = useCallback(
    (event: React.PointerEvent<HTMLInputElement>) => {
      const pointer = pointerRef.current;
      if (!pointer || pointer.pointerId !== event.pointerId) return;

      const hasMoved =
        Math.abs(event.clientX - pointer.x) > MOBILE_TITLE_MOVE_TOLERANCE ||
        Math.abs(event.clientY - pointer.y) > MOBILE_TITLE_MOVE_TOLERANCE;
      if (hasMoved && !pointer.isLongPress) {
        clearPointer();
      }
    },
    [clearPointer],
  );

  const handlePointerUp = useCallback(
    (event: React.PointerEvent<HTMLInputElement>) => {
      const pointer = pointerRef.current;
      if (!pointer || pointer.pointerId !== event.pointerId) return;

      clearLongPress();
      if (pointer.isLongPress) {
        event.preventDefault();
        event.stopPropagation();
        inputRef.current?.blur();
      }
      pointerRef.current = null;
    },
    [clearLongPress],
  );

  const handleContextMenu = useCallback((event: React.MouseEvent<HTMLInputElement>) => {
    if (!pointerRef.current?.isLongPress) return;
    event.preventDefault();
    event.stopPropagation();
    inputRef.current?.blur();
  }, []);

  return (
    <Box py="5">
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onBlur={onBlur}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={clearPointer}
        onContextMenu={handleContextMenu}
        onClick={
          disabled
            ? (event) => {
                event.preventDefault();
                onDisabledClick?.();
              }
            : undefined
        }
        onFocus={
          disabled
            ? (event) => {
                event.target.blur();
                onDisabledClick?.();
              }
            : undefined
        }
        placeholder={placeholder ?? t("writing.titlePlaceholder")}
        readOnly={disabled}
        style={{
          width: "100%",
          border: "none",
          outline: "none",
          background: "transparent",
          fontSize: "2rem",
          fontWeight: 700,
          lineHeight: 1.3,
          color: "var(--gray-12)",
          padding: 0,
          cursor: disabled ? "not-allowed" : "text",
        }}
      />
    </Box>
  );
}
