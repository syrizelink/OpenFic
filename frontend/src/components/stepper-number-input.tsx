import { Flex, TextField } from "@radix-ui/themes";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

const LONG_PRESS_DELAY_MS = 400;
const LONG_PRESS_INTERVAL_MS = 80;

export interface StepperNumberInputProps {
  value: number | string;
  onChange?: (value: string) => void;
  onCommit?: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  unit?: ReactNode;
  width?: number;
  increaseAriaLabel: string;
  decreaseAriaLabel: string;
  disabled?: boolean;
}

function clamp(value: number, min?: number, max?: number): number {
  const lowerBound = min === undefined ? value : Math.max(min, value);
  return max === undefined ? lowerBound : Math.min(max, lowerBound);
}

function roundToStep(value: number, step: number): number {
  return Math.round(value / step) * step;
}

export function StepperNumberInput({
  value,
  onChange,
  onCommit,
  min,
  max,
  step = 1,
  unit,
  width = 200,
  increaseAriaLabel,
  decreaseAriaLabel,
  disabled = false,
}: StepperNumberInputProps) {
  const [draft, setDraft] = useState(() => String(value));
  const draftRef = useRef(String(value));
  const valueRef = useRef(String(value));
  const inputRef = useRef<HTMLInputElement>(null);
  const longPressTimeoutRef = useRef<number | null>(null);
  const longPressIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    const nextValue = String(value);
    draftRef.current = nextValue;
    valueRef.current = nextValue;
    setDraft(nextValue);
  }, [value]);

  const updateDraft = (nextValue: string) => {
    draftRef.current = nextValue;
    setDraft(nextValue);
    onChange?.(nextValue);
  };

  const commit = () => {
    const parsed = Number(draftRef.current);
    if (!Number.isFinite(parsed)) {
      if (onCommit) {
        draftRef.current = valueRef.current;
        setDraft(valueRef.current);
      }
      return;
    }

    const nextValue = clamp(roundToStep(parsed, step), min, max);
    const nextDraft = String(nextValue);
    draftRef.current = nextDraft;
    setDraft(nextDraft);
    onChange?.(nextDraft);
    if (onCommit && nextValue !== Number(valueRef.current)) onCommit(nextValue);
  };

  const stepBy = (delta: number) => {
    const currentValue = Number(draftRef.current);
    const base = Number.isFinite(currentValue) ? currentValue : Number(valueRef.current);
    const nextValue = clamp(base + delta * step, min, max);
    updateDraft(String(nextValue));
    inputRef.current?.focus();
  };

  const stopLongPress = useCallback(() => {
    if (longPressTimeoutRef.current !== null) {
      window.clearTimeout(longPressTimeoutRef.current);
      longPressTimeoutRef.current = null;
    }
    if (longPressIntervalRef.current !== null) {
      window.clearInterval(longPressIntervalRef.current);
      longPressIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    window.addEventListener("pointerup", stopLongPress);
    window.addEventListener("pointercancel", stopLongPress);
    return () => {
      window.removeEventListener("pointerup", stopLongPress);
      window.removeEventListener("pointercancel", stopLongPress);
      stopLongPress();
    };
  }, [stopLongPress]);

  const startLongPress = (delta: number) => {
    stopLongPress();
    stepBy(delta);
    longPressTimeoutRef.current = window.setTimeout(() => {
      longPressIntervalRef.current = window.setInterval(
        () => stepBy(delta),
        LONG_PRESS_INTERVAL_MS,
      );
    }, LONG_PRESS_DELAY_MS);
  };

  const stepperButton = (direction: "up" | "down") => {
    const isUp = direction === "up";
    return (
      <button
        type="button"
        tabIndex={-1}
        aria-label={isUp ? increaseAriaLabel : decreaseAriaLabel}
        disabled={disabled}
        onPointerDown={(event) => {
          if (event.pointerType === "mouse" && event.button !== 0) return;
          event.preventDefault();
          startLongPress(isUp ? 1 : -1);
        }}
        onClick={(event) => {
          if (event.detail === 0) stepBy(isUp ? 1 : -1);
        }}
        className="settings-number-stepper-btn"
      >
        {isUp ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
    );
  };

  return (
    <TextField.Root
      type="number"
      min={min}
      max={max}
      step={step}
      value={draft}
      ref={inputRef}
      onChange={(event) => updateDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur();
      }}
      disabled={disabled}
      className="settings-number-field"
      style={{ width }}
    >
      <TextField.Slot
        side="right"
        className="settings-number-stepper-slot"
      >
        <Flex
          direction="column"
          className="settings-number-stepper"
        >
          {stepperButton("up")}
          {stepperButton("down")}
        </Flex>
      </TextField.Slot>
      {unit ? <TextField.Slot side="right">{unit}</TextField.Slot> : null}
    </TextField.Root>
  );
}
