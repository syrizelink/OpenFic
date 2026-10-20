import { GripHorizontal } from "lucide-react";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
  type PointerEvent,
} from "react";

import type { UIValue } from "./declarative-schema";

export function DeclarativeFloatingPanel({
  forwarded = {},
  position,
  width = 240,
  dragLabel = "Move panel",
  onPositionChange,
  children,
}: {
  forwarded?: Record<string, unknown>;
  position?: UIValue;
  width?: number;
  dragLabel?: string;
  onPositionChange: (position: { x: number; y: number }) => void;
  children: ReactNode;
}) {
  const root = useRef<HTMLDivElement>(null);
  const drag = useRef<{
    pointer: number;
    x: number;
    y: number;
    origin: { x: number; y: number };
  } | null>(null);
  const [location, setLocation] = useState({ x: innerWidth - width - 12, y: innerHeight - 280 });
  const serialized = JSON.stringify(position ?? null);
  const clamp = useCallback(
    (value: { x: number; y: number }) => {
      const bounds = root.current?.getBoundingClientRect();
      return {
        x: Math.max(0, Math.min(innerWidth - (bounds?.width ?? width), value.x)),
        y: Math.max(0, Math.min(innerHeight - (bounds?.height ?? 240) - 28, value.y)),
      };
    },
    [width],
  );
  useEffect(() => {
    const value: unknown = JSON.parse(serialized);
    if (value === null) {
      setLocation(
        clamp({
          x: innerWidth - width - 12,
          y: innerHeight - (root.current?.getBoundingClientRect().height ?? 240) - 40,
        }),
      );
      return;
    }
    if (
      value &&
      typeof value === "object" &&
      "x" in value &&
      "y" in value &&
      typeof value.x === "number" &&
      typeof value.y === "number"
    )
      setLocation(clamp({ x: value.x, y: value.y }));
  }, [serialized, clamp, width]);
  useLayoutEffect(() => {
    const fit = () => setLocation((value) => clamp(value));
    fit();
    window.addEventListener("resize", fit);
    const observer = new ResizeObserver(fit);
    if (root.current) observer.observe(root.current);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", fit);
    };
  }, [clamp]);
  function finish(event: PointerEvent<HTMLButtonElement>, cancelled: boolean) {
    const current = drag.current;
    if (!current || current.pointer !== event.pointerId) return;
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      event.currentTarget.releasePointerCapture(event.pointerId);
    const next = clamp(
      cancelled
        ? current.origin
        : {
            x: current.origin.x + event.clientX - current.x,
            y: current.origin.y + event.clientY - current.y,
          },
    );
    setLocation(next);
    if (!cancelled) onPositionChange(next);
  }
  return (
    <div
      {...Object.fromEntries(
        Object.entries(forwarded).filter(
          ([key]) =>
            !["key", "position", "width", "dragLabel", "onPositionChange", "children"].includes(
              key,
            ),
        ),
      )}
      ref={root}
      className={`plugin-floating-panel ${typeof forwarded.className === "string" ? forwarded.className : ""}`}
      style={{
        ...(forwarded.style as CSSProperties),
        position: "fixed",
        left: location.x,
        top: location.y,
        width: Math.max(96, Math.min(640, width)),
        maxWidth: "calc(100vw - 12px)",
        maxHeight: "calc(100dvh - 40px)",
        overflow: "auto",
        pointerEvents: "auto",
      }}
    >
      <button
        type="button"
        className="plugin-floating-panel-handle"
        aria-label={dragLabel}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.preventDefault();
          drag.current = {
            pointer: event.pointerId,
            x: event.clientX,
            y: event.clientY,
            origin: location,
          };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          const current = drag.current;
          if (current?.pointer === event.pointerId)
            setLocation(
              clamp({
                x: current.origin.x + event.clientX - current.x,
                y: current.origin.y + event.clientY - current.y,
              }),
            );
        }}
        onPointerUp={(event) => finish(event, false)}
        onPointerCancel={(event) => finish(event, true)}
        onKeyDown={(event) => {
          const shifts: Record<string, [number, number]> = {
            ArrowLeft: [-10, 0],
            ArrowRight: [10, 0],
            ArrowUp: [0, -10],
            ArrowDown: [0, 10],
          };
          const shift = shifts[event.key];
          if (!shift) return;
          event.preventDefault();
          const next = clamp({ x: location.x + shift[0], y: location.y + shift[1] });
          setLocation(next);
          onPositionChange(next);
        }}
      >
        <GripHorizontal size={16} />
      </button>
      {children}
    </div>
  );
}
