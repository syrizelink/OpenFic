import { useCallback, useEffect, useRef, useState } from "react";

interface TaskRenameInputProps {
  initialValue: string;
  disabled?: boolean;
  onConfirm: (newTitle: string) => void | Promise<void>;
  onCancel: () => void;
}

export function TaskRenameInput({
  initialValue,
  disabled = false,
  onConfirm,
  onCancel,
}: TaskRenameInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, []);

  const handleSubmit = useCallback(() => {
    const trimmedValue = value.trim();
    if (trimmedValue && trimmedValue !== initialValue) {
      void onConfirm(trimmedValue);
      return;
    }
    onCancel();
  }, [initialValue, onCancel, onConfirm, value]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key === "Enter") {
        event.preventDefault();
        handleSubmit();
      } else if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    },
    [handleSubmit, onCancel]
  );

  return (
    <input
      ref={inputRef}
      type="text"
      value={value}
      disabled={disabled}
      maxLength={200}
      onChange={(event) => setValue(event.target.value)}
      onBlur={handleSubmit}
      onKeyDown={handleKeyDown}
      onClick={(event) => event.stopPropagation()}
      style={{
        width: "100%",
        height: "20px",
        padding: 0,
        margin: 0,
        border: "none",
        outline: "none",
        background: "transparent",
        fontFamily: "inherit",
        fontSize: "14px",
        fontWeight: 500,
        lineHeight: "20px",
        color: "var(--gray-12)",
        boxSizing: "border-box",
      }}
    />
  );
}
