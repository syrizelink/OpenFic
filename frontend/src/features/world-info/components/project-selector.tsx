/**
 * Project Selector Component
 *
 * Komponen kotak tarik-turun pemilih proyek.
 */

import { Box, Flex, Text } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { LabeledSelect } from "@/components/select";
import { fetchProjects } from "@/lib/api-client";
import type { Project } from "@/lib/project.types";

interface ProjectSelectorProps {
  /** ID proyek yang sedang dipilih */
  value: string | null;
  /** Callback pemilihan proyek */
  onChange: (projectId: string) => void;
  /** Status nonaktif */
  disabled?: boolean;
}

export function ProjectSelector({ value, onChange, disabled = false }: ProjectSelectorProps) {
  const { t } = useTranslation();

  // Mengambil daftar proyek
  const { data: projectsData, isLoading } = useQuery({
    queryKey: ["projects", { page: 1, pageSize: 100 }],
    queryFn: () => fetchProjects({ page: 1, pageSize: 100 }),
  });

  const projects = projectsData?.items ?? [];

  // Menemukan proyek yang sedang dipilih
  const selectedProject = projects.find((p: Project) => p.id === value);

  return (
    <Box
      py="2"
      px="4"
      style={{
        borderBottom: "1px solid var(--gray-a5)",
        background: "var(--gray-a2)",
      }}
    >
      <Flex
        align="center"
        gap="3"
      >
        <LabeledSelect
          label={t("worldInfo.selectProject")}
          value={value || ""}
          options={projects.map((project: Project) => ({
            value: project.id,
            label: project.title,
          }))}
          onChange={onChange}
          placeholder={t("worldInfo.selectProjectPlaceholder")}
          disabled={disabled || isLoading}
          layout="horizontal"
          gap="3"
          triggerStyle={{ minWidth: 200 }}
        />
        {selectedProject && (
          <Text
            size="2"
            color="gray"
          >
            {t("worldInfo.projectWorldInfoLabel", { title: selectedProject.title })}
          </Text>
        )}
      </Flex>
    </Box>
  );
}
