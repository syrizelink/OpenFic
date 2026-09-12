/**
 * ProjectFormDialog Component
 *
 * Dialog pembuatan/penyuntingan proyek, memakai validasi React Hook Form + Zod, mendukung unggahan sampul.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { Dialog, Button, Flex, Text, TextField, TextArea, Box } from "@radix-ui/themes";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import type { Project } from "@/lib/project.types";

import { CoverCropper } from "./cover-cropper";

import "./project-form-dialog.css";

interface ProjectFormDialogProps {
  /** Status terbuka dialog */
  open: boolean;
  /** Callback penutupan dialog */
  onOpenChange: (open: boolean) => void;
  /** Callback pengiriman formulir */
  onSubmit: (data: { title: string; description?: string; cover?: File | null }) => void;
  /** Proyek yang sudah ada, diteruskan saat mode sunting */
  project?: Project | null;
  /** Status sedang memuat */
  loading?: boolean;
}

export function ProjectFormDialog({
  open,
  onOpenChange,
  onSubmit,
  project,
  loading = false,
}: ProjectFormDialogProps) {
  const { t } = useTranslation();
  const isEditMode = !!project;
  const [cover, setCover] = useState<File | null>(null);

  /** Schema validasi formulir */
  const projectFormSchema = z.object({
    title: z
      .string()
      .min(1, t("projectForm.titleRequired"))
      .max(200, t("projectForm.titleTooLong")),
    description: z.string().optional(),
  });

  type ProjectFormData = z.infer<typeof projectFormSchema>;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ProjectFormData>({
    resolver: zodResolver(projectFormSchema),
    defaultValues: {
      title: "",
      description: "",
    },
  });

  // Mengisi formulir saat mode sunting
  useEffect(() => {
    if (open && project) {
      reset({
        title: project.title,
        description: project.description ?? "",
      });
    } else if (open && !project) {
      reset({
        title: "",
        description: "",
      });
    }
  }, [open, project, reset]);

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      setCover(null);
      reset({
        title: "",
        description: "",
      });
    }

    onOpenChange(nextOpen);
  };

  const handleFormSubmit = handleSubmit((data) => {
    onSubmit({ ...data, cover });
  });

  return (
    <Dialog.Root
      open={open}
      onOpenChange={handleOpenChange}
      key={open ? "open" : "closed"}
    >
      <Dialog.Content maxWidth="600px">
        <Dialog.Title>
          {isEditMode ? t("projectForm.editProject") : t("projectForm.newProject")}
        </Dialog.Title>
        <Dialog.Description
          size="2"
          color="gray"
        >
          {isEditMode ? t("projectForm.editDescription") : t("projectForm.createDescription")}
        </Dialog.Description>

        <form onSubmit={handleFormSubmit}>
          <Flex
            gap="5"
            mt="4"
            className="project-form-dialog-fields"
          >
            {/* Kiri: sampul */}
            <Box className="project-form-dialog-cover">
              <CoverCropper
                value={cover}
                onChange={setCover}
                previewUrl={project?.coverUrl}
              />
            </Box>

            {/* Kanan: informasi proyek */}
            <Flex
              direction="column"
              gap="4"
              style={{ flex: 1, minWidth: 0 }}
            >
              {/* Judul */}
              <Box>
                <Text
                  as="label"
                  size="2"
                  weight="medium"
                  mb="1"
                  style={{ display: "block" }}
                >
                  {t("projectForm.titleLabel")} <Text color="red">*</Text>
                </Text>
                <TextField.Root
                  placeholder={t("projectForm.titlePlaceholder")}
                  {...register("title")}
                />
                {errors.title && (
                  <Text
                    size="1"
                    color="red"
                    mt="1"
                  >
                    {errors.title.message}
                  </Text>
                )}
              </Box>

              {/* Deskripsi */}
              <Box>
                <Text
                  as="label"
                  size="2"
                  weight="medium"
                  mb="1"
                  style={{ display: "block" }}
                >
                  {t("projectForm.descriptionLabel")}
                </Text>
                <TextArea
                  placeholder={t("projectForm.descriptionPlaceholder")}
                  rows={5}
                  {...register("description")}
                />
              </Box>
            </Flex>
          </Flex>

          <Flex
            gap="3"
            mt="5"
            justify="end"
          >
            <Dialog.Close>
              <Button
                variant="soft"
                color="gray"
                disabled={loading}
              >
                {t("common.cancel")}
              </Button>
            </Dialog.Close>
            <Button
              type="submit"
              loading={loading}
            >
              {isEditMode ? t("common.save") : t("common.create")}
            </Button>
          </Flex>
        </form>
      </Dialog.Content>
    </Dialog.Root>
  );
}
