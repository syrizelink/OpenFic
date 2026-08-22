import { Text, TextField } from "@radix-ui/themes";
import type { ComponentProps } from "react";

export interface UnitTextFieldProps extends ComponentProps<typeof TextField.Root> {
  unit?: string;
  unitSide?: "left" | "right";
  leftUnit?: string;
  rightUnit?: string;
}

export function UnitTextField({
  unit,
  unitSide = "right",
  leftUnit,
  rightUnit,
  children,
  ...props
}: UnitTextFieldProps) {
  const leftUnitValue = leftUnit ?? (unitSide === "left" ? unit : undefined);
  const rightUnitValue = rightUnit ?? (unitSide === "right" ? unit : undefined);

  const renderUnitSlot = (value: string, side: "left" | "right") => (
    <TextField.Slot side={side}>
      <Text
        size="1"
        color="gray"
      >
        {value}
      </Text>
    </TextField.Slot>
  );

  return (
    <TextField.Root
      data-slot="unit-text-field"
      {...props}
    >
      {leftUnitValue ? renderUnitSlot(leftUnitValue, "left") : null}
      {children}
      {rightUnitValue ? renderUnitSlot(rightUnitValue, "right") : null}
    </TextField.Root>
  );
}
