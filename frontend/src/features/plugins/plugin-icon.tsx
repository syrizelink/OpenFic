import type { LucideProps } from "lucide-react";
import { lazy, Suspense } from "react";

const LucideGlyph = lazy(() => import("./lucide-glyph"));

export function PluginIcon({
  name = "Puzzle",
  size = 18,
  ...props
}: LucideProps & { name?: string }) {
  return (
    <Suspense
      fallback={
        <span
          aria-hidden="true"
          style={{ display: "inline-block", width: size, height: size }}
        />
      }
    >
      <LucideGlyph
        name={name}
        size={size}
        aria-hidden="true"
        {...props}
      />
    </Suspense>
  );
}
