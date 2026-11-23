import { Tabs as RadixTabs } from "@radix-ui/themes";
import clsx from "clsx";
import {
  forwardRef,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  type ComponentPropsWithoutRef,
} from "react";

import "./tabs.css";

export type TabsListProps = Omit<ComponentPropsWithoutRef<typeof RadixTabs.List>, "asChild">;

export const TabsList = forwardRef<HTMLDivElement, TabsListProps>(function TabsList(
  { children, className, ...props },
  ref,
) {
  const listRef = useRef<HTMLDivElement>(null);
  const indicatorRef = useRef<HTMLSpanElement>(null);
  useImperativeHandle(ref, () => listRef.current!, []);

  useLayoutEffect(() => {
    const list = listRef.current;
    const indicator = indicatorRef.current;
    if (!list || !indicator) return;
    let isInitialFrame = true;

    const updateIndicator = () => {
      const active = list.querySelector<HTMLElement>('[role="tab"][data-state="active"]');
      if (!active || !active.offsetWidth) {
        delete list.dataset.tabsReady;
        return;
      }
      indicator.style.width = `${active.offsetWidth}px`;
      indicator.style.transform = `translateX(${active.offsetLeft}px)`;
      if (!isInitialFrame) list.dataset.tabsReady = "true";
    };
    const resizeObserver = new ResizeObserver(updateIndicator);
    const observeTabs = () => {
      resizeObserver.disconnect();
      resizeObserver.observe(list);
      list
        .querySelectorAll<HTMLElement>('[role="tab"]')
        .forEach((tab) => resizeObserver.observe(tab));
      updateIndicator();
    };
    const mutationObserver = new MutationObserver(observeTabs);
    mutationObserver.observe(list, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["data-state"],
    });
    observeTabs();
    const frame = requestAnimationFrame(() => {
      isInitialFrame = false;
      updateIndicator();
    });

    return () => {
      cancelAnimationFrame(frame);
      mutationObserver.disconnect();
      resizeObserver.disconnect();
    };
  }, []);

  return (
    <RadixTabs.List
      {...props}
      ref={listRef}
      className={clsx("project-tabs-list", className)}
    >
      {children}
      <span
        ref={indicatorRef}
        className="project-tabs-indicator"
        data-slot="tabs-indicator"
        aria-hidden="true"
      />
    </RadixTabs.List>
  );
});
