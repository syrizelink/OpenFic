import { Text, TextField } from "@radix-ui/themes";
import type { ComponentProps } from "react";

export interface UnitTextFieldProps extends ComponentProps<typeof TextField.Root> {
  unit: string;
  unitSide?: "left" | "right";
}

export function UnitTextField({
  unit,
  unitSide = "right",
  children,
  ...props
}: UnitTextFieldProps) {
  const unitSlot = (
    <TextField.Slot side={unitSide}>
      <Text
        size="1"
        color="gray"
      >
        {unit}
      </Text>
    </TextField.Slot>
  );

  return (
    <TextField.Root
      data-slot="unit-text-field"
      {...props}
    >
      {unitSide === "left" ? unitSlot : null}
      {children}
      {unitSide === "right" ? unitSlot : null}
    </TextField.Root>
  );
}
