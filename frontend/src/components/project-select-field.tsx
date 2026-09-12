/**
 * Project Select Field Component
 *
 * Field pemilihan proyek, memakai panel bentang untuk menampilkan pemilih kisi proyek.
 */

import { Box, TextField, Popover, Text } from "@radix-ui/themes";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { Project } from "@/lib/project.types";

import { ProjectGridSelector } from "./project-grid-selector";

import "./project-select-field.css";

export interface ProjectSelectFieldProps {
  /** Daftar proyek yang bisa dipilih */
  projects: Project[];
  /** ID proyek yang sedang dipilih (string kosong berarti tanpa keterikatan) */
  value: string;
  /** Callback saat proyek dipilih (string kosong berarti tanpa keterikatan) */
  onChange: (projectId: string) => void;
  /** Status nonaktif */
  disabled?: boolean;
  /** Menentukan apakah opsi "tanpa keterikatan" ditampilkan */
  showNoneOption?: boolean;
  /** Teks pengisi sementara */
  placeholder?: string;
  /** Teks label */
  label?: string;
}

export function ProjectSelectField({
  projects,
  value,
  onChange,
  disabled = false,
  showNoneOption = true,
  placeholder,
  label,
}: ProjectSelectFieldProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  // Mengambil proyek yang sedang dipilih
  const selectedProject = value ? projects.find((p) => p.id === value) : null;

  // Teks tampilan (judul ditampilkan bila ada proyek terpilih; bila tidak ada pilihan dan opsi tanpa keterikatan ditampilkan maka "tanpa keterikatan" dipakai; selain itu string kosong agar teks pengisi sementara tampil)
  const displayText = selectedProject
    ? selectedProject.title
    : value === "" && showNoneOption
      ? t("projectSelect.noBinding")
      : "";

  // Menangani pemilihan
  const handleSelect = (projectId: string) => {
    onChange(projectId);
    setOpen(false);
  };

  // Menangani klik pada kotak masukan
  const handleInputClick = () => {
    if (!disabled) {
      setOpen(true);
    }
  };

  return (
    <Box>
      {label && (
        <Text
          as="label"
          size="2"
          weight="medium"
          mb="1"
          className="project-select-field__label"
        >
          {label}
        </Text>
      )}
      <Popover.Root
        open={open}
        onOpenChange={setOpen}
      >
        <Popover.Trigger>
          <Box
            className="project-select-field__trigger"
            data-disabled={disabled ? "true" : "false"}
          >
            <TextField.Root
              value={displayText}
              placeholder={placeholder ?? t("projectSelect.placeholder")}
              disabled={disabled}
              readOnly
              onClick={handleInputClick}
              className="project-select-field__input"
            />
            <Box className="project-select-field__chevron">
              <ChevronDown size={16} />
            </Box>
          </Box>
        </Popover.Trigger>

        <Popover.Content
          className="project-select-field__content"
          align="start"
          side="bottom"
        >
          <ProjectGridSelector
            projects={projects}
            value={value}
            onChange={handleSelect}
            disabled={disabled}
            showNoneOption={showNoneOption}
          />
        </Popover.Content>
      </Popover.Root>
    </Box>
  );
}
