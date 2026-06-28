/**
 * Slider Field Component
 *
 * 滑块参数输入字段，支持滑块和数字输入框联动。
 */

import { Flex, Text, TextField, Slider } from "@radix-ui/themes";
import {
  Controller,
  type Control,
  type FieldValues,
  type Path,
} from "react-hook-form";

interface SliderFieldProps<T extends FieldValues> {
  name: Path<T>;
  label: string;
  description: string;
  control: Control<T>;
  defaultValue: number;
  min: number;
  max: number;
  sliderStep: number;
  inputStep?: number;
  inputKey?: string;
}

export function SliderField<T extends FieldValues>({
  name,
  label,
  description,
  control,
  defaultValue,
  min,
  max,
  sliderStep,
  inputStep,
  inputKey,
}: SliderFieldProps<T>) {
  return (
    <Flex direction="column" gap="2">
      <Flex justify="between" align="center">
        <Text size="2" weight="medium" color="gray">
          {label}
        </Text>
        <Controller
          name={name}
          control={control}
          render={({ field }) => {
            const numValue =
              field.value !== null && field.value !== undefined
                ? (field.value as number)
                : defaultValue;
            const displayValue = String(numValue);
            return (
              <TextField.Root
                key={inputKey ? `${inputKey}-${numValue}` : undefined}
                type="number"
                step={inputStep}
                min={min}
                max={max}
                value={displayValue}
                onChange={(e) => {
                  const val = e.target.value;
                  const numVal = val === "" ? defaultValue : Number(val);
                  field.onChange(numVal);
                }}
                onBlur={field.onBlur}
                style={{ width: 80 }}
              />
            );
          }}
        />
      </Flex>
      <Controller
        name={name}
        control={control}
        render={({ field }) => {
          const sliderValue =
            field.value !== null && field.value !== undefined
              ? (field.value as number)
              : defaultValue;
          return (
            <Slider
              value={[sliderValue]}
              onValueChange={(vals) => {
                field.onChange(vals[0]);
              }}
              min={min}
              max={max}
              step={sliderStep}
              className="model-param-slider"
            />
          );
        }}
      />
      <Text size="1" color="gray">
        {description}
      </Text>
    </Flex>
  );
}
