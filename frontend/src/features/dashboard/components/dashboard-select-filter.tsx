import { useTranslation } from "react-i18next";

import { SimpleSelect } from "@/components/select";

import { EMPTY_VALUE } from "../lib/dashboard-formatters";

interface DashboardSelectFilterProps {
  value?: string;
  placeholder: string;
  options: Array<string | { value: string; label: string }>;
  onChange: (value: string | undefined) => void;
  labelForValue?: (value: string) => string;
}

export function DashboardSelectFilter({
  value,
  placeholder,
  options,
  onChange,
  labelForValue,
}: DashboardSelectFilterProps) {
  const { t } = useTranslation();
  const selectOptions = options.map((option) => {
    if (typeof option === "string") {
      return { value: option, label: labelForValue ? labelForValue(option) : option };
    }
    return option;
  });

  return (
    <SimpleSelect
      value={value || EMPTY_VALUE}
      placeholder={placeholder}
      options={[{ value: EMPTY_VALUE, label: t("dashboard.filters.all") }, ...selectOptions]}
      onChange={(next) => onChange(next === EMPTY_VALUE ? undefined : next)}
    />
  );
}
