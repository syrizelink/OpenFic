import type { ComponentProps } from "react";

import "./spinner.css";

const spinnerSizeClassNames = {
  12: "spinner--12",
  18: "spinner--18",
  24: "spinner--24",
  32: "spinner--32",
} as const;

export interface SpinnerProps extends Omit<ComponentProps<"span">, "children"> {
  size?: 12 | 18 | 24 | 32;
}

export function Spinner({
  size = 24,
  className,
  "aria-label": ariaLabel = "Loading",
  ...props
}: SpinnerProps) {
  const spinnerClassName = className
    ? `spinner ${spinnerSizeClassNames[size]} ${className}`
    : `spinner ${spinnerSizeClassNames[size]}`;

  return (
    <span
      {...props}
      className={spinnerClassName}
      data-slot="spinner"
      role="status"
      aria-label={ariaLabel}
    />
  );
}
