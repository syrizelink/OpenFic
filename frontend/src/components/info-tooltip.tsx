import { Tooltip } from "@radix-ui/themes";
import {
  cloneElement,
  useEffect,
  useId,
  useRef,
  useState,
  type HTMLAttributes,
  type MouseEvent,
  type PointerEvent,
  type ReactElement,
  type ReactNode,
} from "react";

const TOUCH_MEDIA_QUERY = "(hover: none), (pointer: coarse)";
const INFO_TOOLTIP_OPENED_EVENT = "info-tooltip:opened";

interface InfoTooltipProps {
  content: ReactNode;
  children: ReactElement;
}

function useTouchDevice(): boolean {
  const [isTouchDevice, setIsTouchDevice] = useState(
    () => typeof window !== "undefined" && window.matchMedia(TOUCH_MEDIA_QUERY).matches,
  );

  useEffect(() => {
    const mediaQuery = window.matchMedia(TOUCH_MEDIA_QUERY);
    const handleChange = () => setIsTouchDevice(mediaQuery.matches);

    handleChange();
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  return isTouchDevice;
}

export function InfoTooltip({ content, children }: InfoTooltipProps) {
  const isTouchDevice = useTouchDevice();
  const tooltipId = useId();
  const [open, setOpen] = useState(false);
  const pointerDownRef = useRef(false);
  const childProps = children.props as HTMLAttributes<HTMLElement>;

  useEffect(() => {
    if (!isTouchDevice) setOpen(false);
  }, [isTouchDevice]);

  useEffect(() => {
    const handleTooltipOpened = (event: Event) => {
      const { detail } = event as CustomEvent<{ id: string }>;
      if (detail.id !== tooltipId) setOpen(false);
    };

    document.addEventListener(INFO_TOOLTIP_OPENED_EVENT, handleTooltipOpened);
    return () => document.removeEventListener(INFO_TOOLTIP_OPENED_EVENT, handleTooltipOpened);
  }, [tooltipId]);

  useEffect(() => {
    if (!isTouchDevice || !open) return;

    document.dispatchEvent(
      new CustomEvent(INFO_TOOLTIP_OPENED_EVENT, {
        detail: { id: tooltipId },
      }),
    );
  }, [isTouchDevice, open, tooltipId]);

  if (!isTouchDevice) {
    return <Tooltip content={content}>{children}</Tooltip>;
  }

  const handlePointerDown = (event: PointerEvent<HTMLElement>) => {
    childProps.onPointerDown?.(event);
    if (event.defaultPrevented) return;

    event.preventDefault();
    event.stopPropagation();
    pointerDownRef.current = true;
    setOpen((current) => !current);
  };

  const handleClick = (event: MouseEvent<HTMLElement>) => {
    childProps.onClick?.(event);
    if (event.defaultPrevented) return;

    event.preventDefault();
    event.stopPropagation();
    if (pointerDownRef.current) {
      pointerDownRef.current = false;
      return;
    }

    setOpen((current) => !current);
  };

  const trigger = cloneElement(children, {
    onPointerDown: handlePointerDown,
    onClick: handleClick,
  } as Partial<HTMLAttributes<HTMLElement>>);

  return (
    <Tooltip
      content={content}
      open={isTouchDevice ? open : undefined}
      onOpenChange={isTouchDevice ? setOpen : undefined}
    >
      {trigger}
    </Tooltip>
  );
}
