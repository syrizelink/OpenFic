import { Button, Popover } from "@radix-ui/themes";
import { format, parse } from "date-fns";
import { zhCN } from "date-fns/locale";
import { CalendarDays } from "lucide-react";
import { useState } from "react";
import { DayPicker } from "react-day-picker";
import { useTranslation } from "react-i18next";

import "react-day-picker/style.css";

interface DashboardDatePickerProps {
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
  disabled?: { before?: Date; after?: Date };
}

function parseDateValue(value: string): Date | undefined {
  if (!value) return undefined;
  const parsed = parse(value, "yyyy-MM-dd", new Date());
  return Number.isNaN(parsed.getTime()) ? undefined : parsed;
}

function formatDateValue(value: string): string {
  const parsed = parseDateValue(value);
  if (!parsed) return "";
  return format(parsed, "yyyy-MM-dd");
}

export function DashboardDatePicker({ value, placeholder, onChange }: DashboardDatePickerProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const selected = parseDateValue(value);

  const handleSelect = (date: Date | undefined) => {
    onChange(date ? format(date, "yyyy-MM-dd") : "");
    setOpen(false);
  };

  return (
    <Popover.Root
      open={open}
      onOpenChange={setOpen}
    >
      <Popover.Trigger>
        <button
          type="button"
          className="dashboard-date-trigger"
        >
          <span className={value ? "dashboard-date-value" : "dashboard-date-placeholder"}>
            {formatDateValue(value) || placeholder}
          </span>
          <CalendarDays
            size={15}
            className="dashboard-date-icon"
          />
        </button>
      </Popover.Trigger>
      <Popover.Content
        className="dashboard-date-popover"
        sideOffset={6}
        align="start"
      >
        <DayPicker
          mode="single"
          selected={selected}
          onSelect={handleSelect}
          locale={zhCN}
          weekStartsOn={1}
          showOutsideDays
          className="dashboard-day-picker"
        />
        {value ? (
          <div className="dashboard-date-popover-footer">
            <Button
              size="1"
              variant="soft"
              color="gray"
              onClick={() => onChange("")}
            >
              {t("dashboard.filters.clearDate")}
            </Button>
          </div>
        ) : null}
      </Popover.Content>
    </Popover.Root>
  );
}
