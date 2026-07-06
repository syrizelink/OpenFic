/**
 * Auto Save Hook
 *
 * 自动保存 hook，支持定时保存和内容变化检测。
 */

import { useEffect, useState, useRef, useCallback } from "react";

interface UseAutoSaveOptions {
  /** 保存间隔（毫秒），默认 3 分钟 */
  interval?: number;
  /** 是否启用自动保存 */
  enabled?: boolean;
  /** 保存函数 */
  onSave: () => Promise<void>;
  /** 是否有未保存的更改 */
  hasChanges: boolean;
}

/**
 * 自动保存 hook
 *
 * @param options 配置选项
 * @returns 保存状态和手动触发保存的函数
 */
export function useAutoSave({
  interval = 3 * 60 * 1000, // 3 分钟
  enabled = true,
  onSave,
  hasChanges,
}: UseAutoSaveOptions) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [lastSaveTime, setLastSaveTime] = useState<number | null>(null);
  const isSavingRef = useRef(false);

  // 清除定时器
  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // 执行保存
  const save = useCallback(async () => {
    if (isSavingRef.current || !hasChanges) return;

    isSavingRef.current = true;
    try {
      await onSave();
      setLastSaveTime(Date.now());
    } finally {
      isSavingRef.current = false;
    }
  }, [onSave, hasChanges]);

  // 重置定时器
  const resetTimer = useCallback(() => {
    clearTimer();
    if (enabled && hasChanges) {
      timerRef.current = setTimeout(() => {
        save();
      }, interval);
    }
  }, [clearTimer, enabled, hasChanges, interval, save]);

  // 内容变化时重置定时器
  useEffect(() => {
    resetTimer();
    return clearTimer;
  }, [resetTimer, clearTimer]);

  // 页面离开前保存
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasChanges) {
        e.preventDefault();
        // 现代浏览器会忽略自定义消息，但仍需要设置 returnValue
        e.returnValue = "";
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [hasChanges]);

  return {
    save,
    resetTimer,
    lastSaveTime,
  };
}
