import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { StreamingMarkdown } from "@/components";

import {
  appendStreamingBlockContent,
  createStreamingBlockState,
} from "../../lib/streaming-block-splitter";

import "./virtualized-message-content.css";

const VIEWPORT_PADDING_PX = 1_600;
const ESTIMATED_LINE_HEIGHT_PX = 22;
const MIN_BLOCK_HEIGHT_PX = 44;

interface VirtualizedMarkdownContentProps {
  content: string;
  isStreaming?: boolean;
  className?: string;
}

interface BlockRange {
  first: number;
  last: number;
}

function estimateBlockHeight(text: string): number {
  if (text.length === 0) return 0;
  let lines = 1;
  for (let index = 0; index < text.length; index += 1) {
    if (text.charCodeAt(index) === 10) lines += 1;
  }
  return Math.max(lines * ESTIMATED_LINE_HEIGHT_PX, MIN_BLOCK_HEIGHT_PX);
}

function findBlockIndex(offsets: number[], px: number): number {
  if (offsets.length === 0) return -1;
  let low = 0;
  let high = offsets.length;
  while (low < high) {
    const mid = (low + high) >> 1;
    if (offsets[mid] <= px) low = mid + 1;
    else high = mid;
  }
  return Math.min(low - 1, offsets.length - 1);
}

interface VirtualizedBlockProps {
  block: string;
  top: number;
  isStreaming: boolean;
  className?: string;
  blockIndex: number;
  measureBlock: (index: number, el: HTMLDivElement | null) => void;
}

const VirtualizedBlock = memo(
  function VirtualizedBlock({
    block,
    top,
    isStreaming,
    className,
    blockIndex,
    measureBlock,
  }: VirtualizedBlockProps) {
    const handleMeasure = useCallback(
      (el: HTMLDivElement | null) => measureBlock(blockIndex, el),
      [blockIndex, measureBlock],
    );
    return (
      <div
        ref={handleMeasure}
        className="virtualized-markdown-block"
        style={{ top }}
      >
        <StreamingMarkdown
          content={block}
          isStreaming={isStreaming}
          className={className}
        />
      </div>
    );
  },
  (prev, next) =>
    prev.block === next.block &&
    prev.top === next.top &&
    prev.isStreaming === next.isStreaming &&
    prev.className === next.className &&
    prev.blockIndex === next.blockIndex &&
    prev.measureBlock === next.measureBlock,
);

export function VirtualizedMarkdownContent({
  content,
  isStreaming = false,
  className,
}: VirtualizedMarkdownContentProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const prevContentRef = useRef("");
  const splitterStateRef = useRef(createStreamingBlockState());
  const [heights, setHeights] = useState<ReadonlyMap<number, number>>(() => new Map());
  const [range, setRange] = useState<BlockRange | null>(null);
  const rangeRef = useRef<BlockRange | null>(null);

  const splitState = useMemo(() => {
    const prevContent = prevContentRef.current;
    if (prevContent === content) return splitterStateRef.current;
    if (content.startsWith(prevContent)) {
      splitterStateRef.current = appendStreamingBlockContent(
        splitterStateRef.current,
        content.slice(prevContent.length),
      );
    } else {
      splitterStateRef.current = appendStreamingBlockContent(createStreamingBlockState(), content);
    }
    prevContentRef.current = content;
    return splitterStateRef.current;
  }, [content]);

  const { blocks, active } = splitState;

  const blockHeights = useMemo(
    () => blocks.map((block, index) => heights.get(index) ?? estimateBlockHeight(block)),
    [blocks, heights],
  );
  const offsets = useMemo(() => {
    const result: number[] = [];
    let acc = 0;
    for (let index = 0; index < blockHeights.length; index += 1) {
      result.push(acc);
      acc += blockHeights[index];
    }
    return result;
  }, [blockHeights]);
  const activeOffset =
    offsets.length > 0 ? offsets[offsets.length - 1] + blockHeights[blockHeights.length - 1] : 0;
  const activeHeight = heights.get(blocks.length) ?? estimateBlockHeight(active);
  const totalHeight = activeOffset + activeHeight;

  const viewportStateRef = useRef({ offsets, totalHeight, blockCount: blocks.length });
  viewportStateRef.current = { offsets, totalHeight, blockCount: blocks.length };
  const computeRef = useRef<() => void>(() => {});

  useEffect(() => {
    const root = rootRef.current;
    const container = root?.closest(".ai-sidebar-messages");
    if (!root || !(container instanceof HTMLElement)) return;

    const compute = () => {
      const {
        offsets: blockOffsets,
        totalHeight: rootHeight,
        blockCount,
      } = viewportStateRef.current;
      let nextRange: BlockRange | null = null;
      if (blockCount > 0 && rootHeight > 0) {
        const containerRect = container.getBoundingClientRect();
        const rootRect = root.getBoundingClientRect();
        const elTop = rootRect.top - containerRect.top + container.scrollTop;
        const viewStart = container.scrollTop;
        const viewEnd = viewStart + container.clientHeight;
        const start = Math.max(0, viewStart - elTop);
        const end = Math.min(rootHeight, viewEnd - elTop);
        if (end > 0 && start < rootHeight && blockOffsets.length > 0) {
          const first = Math.max(
            0,
            findBlockIndex(blockOffsets, Math.max(0, start - VIEWPORT_PADDING_PX)),
          );
          const last = Math.min(
            blockCount - 1,
            findBlockIndex(blockOffsets, Math.min(rootHeight, end + VIEWPORT_PADDING_PX)),
          );
          nextRange = { first, last };
        }
      }
      const previousRange = rangeRef.current;
      if (
        nextRange === previousRange ||
        (nextRange !== null &&
          previousRange !== null &&
          nextRange.first === previousRange.first &&
          nextRange.last === previousRange.last)
      ) {
        return;
      }
      rangeRef.current = nextRange;
      setRange(nextRange);
    };

    computeRef.current = compute;
    compute();
    container.addEventListener("scroll", compute, { passive: true });
    const resizeObserver = new ResizeObserver(compute);
    resizeObserver.observe(container);
    resizeObserver.observe(root);
    return () => {
      computeRef.current = () => {};
      container.removeEventListener("scroll", compute);
      resizeObserver.disconnect();
      if (heightsFlushRafRef.current !== null) {
        window.cancelAnimationFrame(heightsFlushRafRef.current);
        heightsFlushRafRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    computeRef.current();
  }, [blocks, heights]);

  const pendingHeightsRef = useRef<Map<number, number>>(new Map());
  const heightsFlushRafRef = useRef<number | null>(null);

  const measureBlock = useCallback((index: number, el: HTMLDivElement | null) => {
    if (!el) return;
    const height = el.offsetHeight;
    pendingHeightsRef.current.set(index, height);
    if (heightsFlushRafRef.current === null) {
      heightsFlushRafRef.current = window.requestAnimationFrame(() => {
        heightsFlushRafRef.current = null;
        const pending = pendingHeightsRef.current;
        pendingHeightsRef.current = new Map();
        setHeights((previous) => {
          let changed = false;
          const next = new Map(previous);
          for (const [indexToSet, heightToSet] of pending) {
            if (next.get(indexToSet) !== heightToSet) {
              next.set(indexToSet, heightToSet);
              changed = true;
            }
          }
          return changed ? next : previous;
        });
      });
    }
  }, []);

  const windowBlocks = useMemo(() => {
    if (!range) return [];
    const result: number[] = [];
    for (let index = range.first; index <= range.last; index += 1) {
      result.push(index);
    }
    return result;
  }, [range]);

  return (
    <div
      ref={rootRef}
      className="virtualized-markdown"
      style={{ height: totalHeight }}
    >
      {" "}
      {windowBlocks.map((index) => (
        <VirtualizedBlock
          key={index}
          block={blocks[index]}
          top={offsets[index]}
          isStreaming={false}
          className={className}
          blockIndex={index}
          measureBlock={measureBlock}
        />
      ))}
      {active.length > 0 ? (
        <VirtualizedBlock
          block={active}
          top={activeOffset}
          isStreaming={isStreaming}
          className={className}
          blockIndex={blocks.length}
          measureBlock={measureBlock}
        />
      ) : null}
    </div>
  );
}
