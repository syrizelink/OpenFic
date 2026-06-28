/**
 * UI Utils
 *
 * UI 相关的工具函数。
 */

import { toast } from "@/components";

/**
 * 根据项目 ID 生成一个稳定的渐变色
 * 使用简单的哈希算法，基于字符串生成一致的渐变背景
 */
export function generateGradient(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = id.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue1 = Math.abs(hash % 360);
  const hue2 = (hue1 + 40) % 360;
  return `linear-gradient(135deg, hsl(${hue1}, 70%, 60%) 0%, hsl(${hue2}, 60%, 50%) 100%)`;
}

export function createToastThrottler(message: string, delay = 1200) {
  let lastShown = 0;

  return () => {
    const now = Date.now();
    if (now - lastShown < delay) return;
    lastShown = now;
    toast.info(message);
  };
}
