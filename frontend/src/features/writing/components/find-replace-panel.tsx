/**
 * Find Replace Panel
 *
 * Komponen panel cari dan ganti, menyediakan masukan pencarian, navigasi hasil, dan fungsi penggantian.
 */

import { Box, Flex, IconButton, Text, Separator, Tooltip } from "@radix-ui/themes";
import type { Editor } from "@tiptap/react";
import { X, ChevronUp, ChevronDown, Replace, ReplaceAll, Search } from "lucide-react";
import { motion } from "motion/react";
import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";

interface FindReplacePanelProps {
  editor: Editor;
  /** Menampilkan area penggantian (saat false hanya pencarian yang tampil) */
  showReplace: boolean;
  /** Callback untuk menutup panel */
  onClose: () => void;
}

/** Lebar maksimum kotak pencarian (sama dengan isi editor) */
const PANEL_MAX_WIDTH = 800;

/** Gaya kotak masukan pencarian */
const inputStyle: React.CSSProperties = {
  flex: 1,
  height: 32,
  padding: "0 8px",
  paddingLeft: 32, // Menyisakan ruang untuk ikon pencarian
  paddingRight: 56, // Menyisakan ruang untuk penghitung
  fontFamily: "var(--app-font-family)",
  fontSize: "var(--font-size-base)",
  border: "1px solid var(--gray-a5)",
  borderRadius: 6,
  background: "var(--color-background)",
  color: "var(--gray-12)",
  outline: "none",
  transition: "border-color 0.2s ease, box-shadow 0.2s ease",
};

/** Gaya kotak masukan penggantian */
const replaceInputStyle: React.CSSProperties = {
  flex: 1,
  height: 32,
  padding: "0 8px",
  paddingLeft: 12,
  fontFamily: "var(--app-font-family)",
  fontSize: "var(--font-size-base)",
  border: "1px solid var(--gray-a5)",
  borderRadius: 6,
  background: "var(--color-background)",
  color: "var(--gray-12)",
  outline: "none",
  transition: "border-color 0.2s ease, box-shadow 0.2s ease",
};

export function FindReplacePanel({ editor, showReplace, onClose }: FindReplacePanelProps) {
  const { t } = useTranslation();
  const [searchTerm, setSearchTerm] = useState("");
  const [replaceTerm, setReplaceTerm] = useState("");
  const [searchFocused, setSearchFocused] = useState(false);
  const [replaceFocused, setReplaceFocused] = useState(false);

  // Status hasil pencarian (disinkronkan dari editor storage)
  const [resultCount, setResultCount] = useState(0);
  const [currentIndex, setCurrentIndex] = useState(0);

  // Menyinkronkan kata pencarian ke editor
  useEffect(() => {
    editor.commands.setSearchTerm(searchTerm);
  }, [editor, searchTerm]);

  // Memantau pembaruan editor, menyinkronkan hasil pencarian ke state komponen
  useEffect(() => {
    const updateResults = () => {
      const storage = (editor as any).storage.searchAndReplace as
        | {
            results: Array<{ from: number; to: number }>;
            resultIndex: number;
          }
        | undefined;
      const results = storage?.results ?? [];
      const resultIndex = storage?.resultIndex ?? 0;
      setResultCount(results.length);
      setCurrentIndex(results.length > 0 ? resultIndex + 1 : 0);
    };

    // Pembaruan awal
    updateResults();

    // Memantau pembaruan transaksi
    editor.on("transaction", updateResults);
    return () => {
      editor.off("transaction", updateResults);
    };
  }, [editor]);

  // Menyinkronkan kata penggantian ke editor
  useEffect(() => {
    editor.commands.setReplaceTerm(replaceTerm);
  }, [editor, replaceTerm]);

  // Membersihkan pencarian saat ditutup
  useEffect(() => {
    return () => {
      editor.commands.setSearchTerm("");
      editor.commands.setReplaceTerm("");
    };
  }, [editor]);

  // Tombol ESC menutup panel
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Menggulir ke hasil pencarian saat ini
  const scrollToCurrentResult = useCallback(() => {
    const storage = (editor as any).storage.searchAndReplace;
    const results = storage?.results ?? [];
    const resultIndex = storage?.resultIndex ?? 0;
    const currentResult = results[resultIndex];

    if (currentResult) {
      // Memakai sistem koordinat ProseMirror untuk mengambil posisi lalu menggulir
      const { from } = currentResult;
      const coords = editor.view.coordsAtPos(from);
      const editorElement = editor.view.dom.closest(".tiptap-editor-wrapper") as HTMLElement;

      if (editorElement && coords) {
        const editorRect = editorElement.getBoundingClientRect();
        const relativeTop = coords.top - editorRect.top + editorElement.scrollTop;

        // Menggulir agar hasilnya berada di tengah tampilan
        editorElement.scrollTo({
          top: relativeTop - editorRect.height / 2,
          behavior: "smooth",
        });
      }
    }
  }, [editor]);

  const handlePrevious = useCallback(() => {
    editor.commands.previousSearchResult();
    // Menunda gulir, menunggu pembaruan DOM
    setTimeout(scrollToCurrentResult, 10);
  }, [editor, scrollToCurrentResult]);

  const handleNext = useCallback(() => {
    editor.commands.nextSearchResult();
    // Menunda gulir, menunggu pembaruan DOM
    setTimeout(scrollToCurrentResult, 10);
  }, [editor, scrollToCurrentResult]);

  const handleReplace = useCallback(() => {
    editor.commands.replace();
  }, [editor]);

  const handleReplaceAll = useCallback(() => {
    editor.commands.replaceAll();
  }, [editor]);

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.06, ease: "easeOut" }}
      style={{
        overflow: "hidden",
        background: "var(--color-background)",
      }}
    >
      <Box py="3">
        {/* Wadah tengah, lebarnya sama dengan isi editor */}
        <Box
          style={{
            maxWidth: PANEL_MAX_WIDTH,
            margin: "0 auto",
            padding: "0 24px",
          }}
        >
          <Flex
            direction="column"
            gap="2"
          >
            {/* Baris pencarian */}
            <Flex
              align="center"
              gap="2"
            >
              {/* Wadah kotak masukan pencarian */}
              <Box style={{ flex: 1, position: "relative" }}>
                {/* Ikon pencarian */}
                <Box
                  style={{
                    position: "absolute",
                    left: 10,
                    top: "50%",
                    transform: "translateY(-50%)",
                    pointerEvents: "none",
                    color: "var(--gray-a9)",
                  }}
                >
                  <Search size={14} />
                </Box>

                {/* Kotak masukan pencarian */}
                <input
                  type="text"
                  placeholder={t("editor.findPlaceholder")}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  onFocus={() => setSearchFocused(true)}
                  onBlur={() => setSearchFocused(false)}
                  autoFocus
                  style={{
                    ...inputStyle,
                    width: "100%",
                    borderColor: searchFocused ? "var(--gray-a8)" : "var(--gray-a5)",
                    boxShadow: searchFocused ? "0 0 0 1px var(--gray-a4)" : "none",
                  }}
                />

                {/* Penghitung hasil (di sisi kanan dalam kotak pencarian) */}
                <Text
                  size="1"
                  color="gray"
                  style={{
                    position: "absolute",
                    right: 10,
                    top: "50%",
                    transform: "translateY(-50%)",
                    pointerEvents: "none",
                    whiteSpace: "nowrap",
                  }}
                >
                  {resultCount > 0 ? `${currentIndex}/${resultCount}` : "0/0"}
                </Text>
              </Box>

              {/* Sebelumnya/berikutnya */}
              <Flex gap="1">
                <Tooltip content={t("editor.previousResult")}>
                  <IconButton
                    variant="ghost"
                    size="1"
                    disabled={resultCount === 0}
                    onClick={handlePrevious}
                    aria-label={t("editor.previousResult")}
                  >
                    <ChevronUp size={16} />
                  </IconButton>
                </Tooltip>
                <Tooltip content={t("editor.nextResult")}>
                  <IconButton
                    variant="ghost"
                    size="1"
                    disabled={resultCount === 0}
                    onClick={handleNext}
                    aria-label={t("editor.nextResult")}
                  >
                    <ChevronDown size={16} />
                  </IconButton>
                </Tooltip>
              </Flex>

              <Separator
                orientation="vertical"
                size="1"
              />

              {/* Tombol tutup */}
              <Tooltip content={t("common.close")}>
                <IconButton
                  variant="ghost"
                  size="1"
                  onClick={onClose}
                  aria-label={t("common.close")}
                >
                  <X size={16} />
                </IconButton>
              </Tooltip>
            </Flex>

            {/* Baris penggantian */}
            {showReplace && (
              <Flex
                align="center"
                gap="2"
              >
                {/* Kotak masukan penggantian */}
                <Box style={{ flex: 1 }}>
                  <input
                    type="text"
                    placeholder={t("editor.replacePlaceholder")}
                    value={replaceTerm}
                    onChange={(e) => setReplaceTerm(e.target.value)}
                    onFocus={() => setReplaceFocused(true)}
                    onBlur={() => setReplaceFocused(false)}
                    style={{
                      ...replaceInputStyle,
                      width: "100%",
                      borderColor: replaceFocused ? "var(--gray-a8)" : "var(--gray-a5)",
                      boxShadow: replaceFocused ? "0 0 0 1px var(--gray-a4)" : "none",
                    }}
                  />
                </Box>

                {/* Tombol ganti/ganti semua */}
                <Flex gap="1">
                  <Tooltip content={t("editor.replace")}>
                    <IconButton
                      variant="ghost"
                      size="1"
                      disabled={resultCount === 0}
                      onClick={handleReplace}
                      aria-label={t("editor.replace")}
                    >
                      <Replace size={16} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip content={t("editor.replaceAll")}>
                    <IconButton
                      variant="ghost"
                      size="1"
                      disabled={resultCount === 0}
                      onClick={handleReplaceAll}
                      aria-label={t("editor.replaceAll")}
                    >
                      <ReplaceAll size={16} />
                    </IconButton>
                  </Tooltip>
                </Flex>

                {/* Pengisi ruang agar tetap sejajar dengan baris sebelumnya */}
                <Box style={{ width: 28 }} />
              </Flex>
            )}
          </Flex>
        </Box>
      </Box>
    </motion.div>
  );
}
