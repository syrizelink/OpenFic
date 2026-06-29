import type { ComponentProps } from "react";
import { motion, useReducedMotion } from "motion/react";

import "./circular-progress.css";

interface CircularProgressProps extends Omit<ComponentProps<"span">, "children"> {
  value: number;
  max?: number;
  size?: number;
  strokeWidth?: number;
  ariaLabel?: string;
}

export function CircularProgress({
  value,
  max = 100,
  size = 16,
  strokeWidth = 1.75,
  className,
  ariaLabel,
  ...props
}: CircularProgressProps) {
  const shouldReduceMotion = useReducedMotion();
  const safeMax = Number.isFinite(max) && max > 0 ? max : 0;
  const safeValue = Number.isFinite(value) ? Math.max(value, 0) : 0;
  const clampedValue = safeMax > 0 ? Math.min(safeValue, safeMax) : 0;
  const progress = safeMax > 0 ? clampedValue / safeMax : 0;
  const boundedProgress = Math.min(1, Math.max(0, progress));
  const center = size / 2;
  const radius = Math.max(0, center - strokeWidth / 2);
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference * (1 - boundedProgress);
  const rootClassName = ["circular-progress", className].filter(Boolean).join(" ");

  return (
    <span {...props} className={rootClassName}>
      <svg
        className="circular-progress__svg"
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="progressbar"
        aria-label={ariaLabel}
        aria-valuemin={0}
        aria-valuemax={safeMax || 100}
        aria-valuenow={Math.round(clampedValue)}
      >
        <circle
          className="circular-progress__track"
          cx={center}
          cy={center}
          r={radius}
          strokeWidth={strokeWidth}
        />
        <motion.circle
          className="circular-progress__indicator"
          initial={false}
          cx={center}
          cy={center}
          r={radius}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          animate={{ strokeDashoffset }}
          transition={
            shouldReduceMotion
              ? { duration: 0 }
              : { duration: 0.35, ease: [0.22, 1, 0.36, 1] }
          }
          transform={`rotate(-90 ${center} ${center})`}
        />
      </svg>
    </span>
  );
}
