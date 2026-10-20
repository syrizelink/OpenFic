import { icons, type LucideProps } from "lucide-react";

const names = new Map(
  Object.keys(icons).map((name) => [name.replaceAll("-", "").toLowerCase(), name]),
);

/** One deferred chunk for the installed icon set, shared by all plugin views. */
export default function LucideGlyph({ name, ...props }: LucideProps & { name: string }) {
  const canonical =
    names.get((typeof name === "string" ? name : "Puzzle").replaceAll("-", "").toLowerCase()) ??
    "Puzzle";
  const Glyph = icons[canonical as keyof typeof icons];
  return (
    <Glyph
      {...props}
      data-lucide={canonical}
    />
  );
}
