/**
 * Model Selector Dialog
 *
 * Dialog pemilih model, dipakai untuk memilih model dari daftar model sebuah penyedia.
 */

import { Dialog, Flex, Button, Text, TextField, Box } from "@radix-ui/themes";
import { Search } from "lucide-react";
import { motion } from "motion/react";
import { useState, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import type { AvailableModel } from "@/lib/model.types";

const MotionBox = motion.create(Box);

interface ModelSelectorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  models: AvailableModel[];
  isLoading: boolean;
  onSelect: (model: AvailableModel) => void;
}

export function ModelSelectorDialog({
  open,
  onOpenChange,
  models,
  isLoading,
  onSelect,
}: ModelSelectorDialogProps) {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState("");

  // Menyaring model
  const filteredModels = useMemo(() => {
    if (!searchQuery.trim()) return models;

    const query = searchQuery.toLowerCase();
    return models.filter(
      (model) => model.id.toLowerCase().includes(query) || model.name.toLowerCase().includes(query),
    );
  }, [models, searchQuery]);

  // Memilih model
  const handleSelect = useCallback(
    (model: AvailableModel) => {
      onSelect(model);
      setSearchQuery("");
    },
    [onSelect],
  );

  // Menangani penutupan dialog
  const handleOpenChange = useCallback(
    (newOpen: boolean) => {
      if (!newOpen) {
        setSearchQuery("");
      }
      onOpenChange(newOpen);
    },
    [onOpenChange],
  );

  return (
    <Dialog.Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Dialog.Content maxWidth="600px">
        <Dialog.Title>{t("models.selectModel")}</Dialog.Title>

        <Flex
          direction="column"
          gap="4"
          mt="4"
        >
          {/* Kotak pencarian */}
          <TextField.Root
            placeholder={t("models.searchModel")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          >
            <TextField.Slot>
              <Search size={16} />
            </TextField.Slot>
          </TextField.Root>

          {/* Daftar model */}
          <Box
            style={{
              maxHeight: 400,
              overflow: "auto",
              border: "1px solid var(--gray-a4)",
              borderRadius: "var(--radius-2)",
            }}
          >
            {isLoading ? (
              <Flex
                align="center"
                justify="center"
                style={{ height: 200, padding: 20 }}
              >
                <Spinner size={18} />
                <Text
                  size="2"
                  color="gray"
                  ml="2"
                >
                  {t("models.loadingModels")}
                </Text>
              </Flex>
            ) : filteredModels.length > 0 ? (
              <Flex direction="column">
                {filteredModels.map((model) => (
                  <MotionBox
                    key={model.id}
                    onClick={() => handleSelect(model)}
                    style={{
                      padding: "12px 16px",
                      cursor: "pointer",
                      borderBottom: "1px solid var(--gray-a3)",
                    }}
                    whileHover={{ backgroundColor: "var(--gray-a2)" }}
                    whileTap={{ scale: 0.98 }}
                    transition={{ duration: 0.15 }}
                  >
                    <Flex
                      direction="column"
                      gap="1"
                    >
                      <Text
                        size="2"
                        weight="medium"
                      >
                        {model.name}
                      </Text>
                      <Text
                        size="1"
                        color="gray"
                      >
                        {model.id}
                      </Text>
                    </Flex>
                  </MotionBox>
                ))}
              </Flex>
            ) : (
              <Flex
                align="center"
                justify="center"
                direction="column"
                gap="2"
                style={{ height: 200, padding: 20 }}
              >
                <Text
                  size="2"
                  color="gray"
                >
                  {searchQuery ? t("projects.noProjectsFound") : t("models.noModels")}
                </Text>
              </Flex>
            )}
          </Box>

          {/* Tombol tutup */}
          <Flex justify="end">
            <Dialog.Close>
              <Button
                variant="soft"
                color="gray"
              >
                {t("common.close")}
              </Button>
            </Dialog.Close>
          </Flex>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
