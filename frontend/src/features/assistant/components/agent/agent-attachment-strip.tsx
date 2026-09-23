import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  useCallback,
  useLayoutEffect,
  useRef,
  useState,
  type ComponentProps,
  type ReactNode,
  type WheelEvent,
} from "react";

interface AgentAttachmentStripProps extends Omit<ComponentProps<"div">, "children" | "onWheel"> {
  children: ReactNode;
  previousLabel: string;
  nextLabel: string;
}

const ATTACHMENT_SCROLL_DISTANCE = 268;

function handleAttachmentWheel(event: WheelEvent<HTMLDivElement>) {
  const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
  if (!delta || event.currentTarget.scrollWidth <= event.currentTarget.clientWidth) return;

  event.preventDefault();
  event.currentTarget.scrollLeft += delta;
}

export function AgentAttachmentStrip({
  children,
  className,
  previousLabel,
  nextLabel,
  ...props
}: AgentAttachmentStripProps) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [scrollEdges, setScrollEdges] = useState({ canScrollLeft: false, canScrollRight: false });
  const stripClassName = ["agent-attachment-strip", className].filter(Boolean).join(" ");
  const updateScrollEdges = useCallback(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    const canScrollLeft = viewport.scrollLeft > 1;
    const canScrollRight = viewport.scrollLeft + viewport.clientWidth < viewport.scrollWidth - 1;
    setScrollEdges((current) =>
      current.canScrollLeft === canScrollLeft && current.canScrollRight === canScrollRight
        ? current
        : { canScrollLeft, canScrollRight },
    );
  }, []);

  useLayoutEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    updateScrollEdges();
    viewport.addEventListener("scroll", updateScrollEdges, { passive: true });
    if (typeof ResizeObserver === "undefined") {
      return () => viewport.removeEventListener("scroll", updateScrollEdges);
    }

    const resizeObserver = new ResizeObserver(updateScrollEdges);
    resizeObserver.observe(viewport);
    return () => {
      viewport.removeEventListener("scroll", updateScrollEdges);
      resizeObserver.disconnect();
    };
  }, [children, updateScrollEdges]);

  const handleScrollClick = (direction: -1 | 1) => {
    viewportRef.current?.scrollBy({
      left: direction * ATTACHMENT_SCROLL_DISTANCE,
      behavior: "smooth",
    });
  };

  return (
    <div className="agent-attachment-strip-shell">
      {scrollEdges.canScrollLeft ? (
        <button
          type="button"
          className="agent-attachment-scroll-button"
          data-direction="left"
          aria-label={previousLabel}
          onClick={(event) => {
            event.stopPropagation();
            handleScrollClick(-1);
          }}
        >
          <ChevronLeft size={18} />
        </button>
      ) : null}
      <div
        {...props}
        ref={viewportRef}
        className={stripClassName}
        onWheel={handleAttachmentWheel}
      >
        {children}
      </div>
      {scrollEdges.canScrollRight ? (
        <button
          type="button"
          className="agent-attachment-scroll-button"
          data-direction="right"
          aria-label={nextLabel}
          onClick={(event) => {
            event.stopPropagation();
            handleScrollClick(1);
          }}
        >
          <ChevronRight size={18} />
        </button>
      ) : null}
    </div>
  );
}
