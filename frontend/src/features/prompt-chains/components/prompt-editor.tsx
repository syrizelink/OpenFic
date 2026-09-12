/**
 * PromptEditor Component
 *
 * Editor prompt (berbasis Tiptap)
 */

import { Flex, TextField, Separator, Text } from "@radix-ui/themes";
import Placeholder from "@tiptap/extension-placeholder";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Terminal, Bot, User } from "lucide-react";
import { useEffect, useRef, useCallback, useState } from "react";

import "./prompt-editor.css";
import { useTranslation } from "react-i18next";

import { ContextMenu } from "@/components";
import { LabeledSelect } from "@/components/select";
import { newlinesToHtml } from "@/lib/html-utils";
import type { PromptEntryData } from "@/lib/prompt-chain.types";
import { countTokens } from "@/lib/tiktoken-utils";

interface PromptEditorProps {
  entry: PromptEntryData;
  onUpdate: (updates: Partial<PromptEntryData>) => void;
  onUpdateWithId?: (entryId: string, updates: Partial<PromptEntryData>) => void;
  isMobile?: boolean;
}

export function PromptEditor({
  entry,
  onUpdate,
  onUpdateWithId,
  isMobile = false,
}: PromptEditorProps) {
  const { t } = useTranslation();
  // entry.id sebelumnya, dipakai untuk mendeteksi perpindahan entri
  const lastEntryIdRef = useRef<string | undefined>(entry.id);
  // Handler peristiwa Tiptap tidak ikut diperbarui oleh props React setelah inisialisasi, jadi konteks terbaru diakses lewat ref.
  const currentEntryIdRef = useRef(entry.id ?? "");
  const onUpdateRef = useRef(onUpdate);
  const onUpdateWithIdRef = useRef(onUpdateWithId);
  // Menandai isi sedang disetel dari luar (mencegah pembaruan berulang)
  const isSettingContentRef = useRef(false);
  // Isi entri terakhir yang disinkronkan dari editor ke komponen induk, mencegah induk memantulkan balik dan mereset kursor.
  const lastSyncedEntryRef = useRef({ id: entry.id, content: entry.content });
  // Isi terakhir yang disimpan (untuk menilai adanya perubahan belum tersimpan, disimpan sebagai HTML agar bisa dibandingkan dengan isi editor)
  const lastSavedContentRef = useRef<string>(
    entry.content ? newlinesToHtml(entry.content, true) : "",
  );
  // Referensi wadah isi editor (dipakai untuk menu klik kanan)
  const editorContentRef = useRef<HTMLDivElement>(null);
  // Jumlah token saat ini
  const [tokenCount, setTokenCount] = useState<number>(entry.token_count || 0);

  currentEntryIdRef.current = entry.id ?? "";
  onUpdateRef.current = onUpdate;
  onUpdateWithIdRef.current = onUpdateWithId;

  // Opsi peran (memakai prefix untuk menampilkan ikon)
  const roleOptions = [
    { value: "system", label: t("promptChains.roleSystem"), prefix: <Terminal size={14} /> },
    { value: "user", label: t("promptChains.roleUser"), prefix: <User size={14} /> },
    { value: "assistant", label: t("promptChains.roleAssistant"), prefix: <Bot size={14} /> },
  ];

  // Pembaruan langsung (untuk field non-isi seperti peran dan nama)
  const immediateUpdate = useCallback((updates: Partial<PromptEntryData>) => {
    if (onUpdateWithIdRef.current) {
      onUpdateWithIdRef.current(currentEntryIdRef.current, updates);
      return;
    }

    onUpdateRef.current(updates);
  }, []);

  const updateEntry = useCallback((entryId: string, updates: Partial<PromptEntryData>) => {
    if (onUpdateWithIdRef.current) {
      onUpdateWithIdRef.current(entryId, updates);
      return;
    }

    onUpdateRef.current(updates);
  }, []);

  // Membuat instans editor
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // Menonaktifkan fitur yang tidak diperlukan
        heading: false,
        bold: false,
        italic: false,
        strike: false,
        code: false,
        codeBlock: false,
        blockquote: false,
        horizontalRule: false,
        bulletList: false,
        orderedList: false,
        listItem: false,
      }),
      Placeholder.configure({
        placeholder: t("promptChains.contentPlaceholder"),
      }),
    ],
    // Saat dimuat dari basis data, ubah karakter baris baru menjadi HTML (format <p></p>) agar bisa ditampilkan Tiptap
    content: entry.content ? newlinesToHtml(entry.content, true) : "",
    parseOptions: {
      preserveWhitespace: "full",
    },
    editorProps: {
      attributes: {
        class: "prompt-editor-content",
      },
    },
    onUpdate: ({ editor }) => {
      // Lewati pembaruan jika isi sedang disetel dari luar
      if (isSettingContentRef.current) {
        return;
      }

      // Ekspor teks polos langsung dari dokumen Tiptap agar HTML tidak diurai ulang secara merusak.
      const html = editor.getHTML();
      const content = editor.getText({ blockSeparator: "\n" });

      const calculatedTokenCount = countTokens(content);
      // Perbarui tampilan jumlah token secara langsung
      setTokenCount(calculatedTokenCount);

      // Penyimpanan versi bergantung pada state entries induk, jadi isi utama harus diperbarui dalam peristiwa ini.
      const entryId = currentEntryIdRef.current;
      lastSyncedEntryRef.current = { id: entryId, content };
      updateEntry(entryId, {
        content: content,
        token_count: calculatedTokenCount,
      });
      lastSavedContentRef.current = html;
    },
  });

  // Menyimpan isi saat ini seketika (untuk pintasan papan tombol dan saat berpindah entri)
  const saveNow = useCallback(() => {
    if (!editor || isSettingContentRef.current) return;

    // Mengambil isi editor saat ini
    const html = editor.getHTML();
    const content = editor.getText({ blockSeparator: "\n" });
    const calculatedTokenCount = countTokens(content);

    // Pembaruan langsung
    lastSyncedEntryRef.current = { id: currentEntryIdRef.current, content };
    updateEntry(currentEntryIdRef.current, {
      content: content,
      token_count: calculatedTokenCount,
    });

    // Memperbarui status penyimpanan
    lastSavedContentRef.current = html;
    setTokenCount(calculatedTokenCount);
  }, [editor, updateEntry]);

  // Fungsi penyimpanan dengan ID entri (dipakai untuk menyimpan entri lama saat berpindah)
  const saveNowWithId = useCallback(
    (targetEntryId: string) => {
      if (!editor || isSettingContentRef.current) return;

      // Mengambil isi editor saat ini
      const html = editor.getHTML();
      const content = editor.getText({ blockSeparator: "\n" });
      const calculatedTokenCount = countTokens(content);

      lastSyncedEntryRef.current = { id: targetEntryId, content };
      updateEntry(targetEntryId, {
        content: content,
        token_count: calculatedTokenCount,
      });

      // Memperbarui status penyimpanan
      lastSavedContentRef.current = html;
      setTokenCount(calculatedTokenCount);
    },
    [editor, updateEntry],
  );

  // Memantau perubahan entry.id agar isi entri lama tersimpan sebelum berpindah
  useEffect(() => {
    if (!editor) return;

    // Mendeteksi perpindahan entri (entry.id berubah)
    const isEntryChanged = lastEntryIdRef.current !== entry.id;
    const previousEntryId = lastEntryIdRef.current;

    // Jika berpindah entri dan ada perubahan belum tersimpan, simpan dulu isi entri lama
    if (isEntryChanged && previousEntryId !== undefined) {
      // Mengambil isi editor saat ini (format HTML)
      const currentEditorContent = editor.getHTML();
      // Memeriksa langsung apakah isi saat ini berbeda dari isi yang sudah disimpan
      const hasChanges = currentEditorContent !== lastSavedContentRef.current;

      if (hasChanges) {
        // Memanggil fungsi penyimpanan (setState ada di dalam useCallback, jadi tidak memicu peringatan)
        saveNowWithId(previousEntryId);
      }
    }

    // Memperbarui lastEntryIdRef (setelah penyimpanan selesai)
    lastEntryIdRef.current = entry.id;
  }, [entry.id, editor, saveNowWithId]);

  // Memperbarui isi editor saat entri atau isi dari luar berubah
  useEffect(() => {
    if (!editor) return;

    const isLocalContentEcho =
      lastSyncedEntryRef.current.id === entry.id &&
      lastSyncedEntryRef.current.content === entry.content;
    if (isLocalContentEcho) return;

    // Mengambil isi editor saat ini (format HTML)
    const currentEditorContent = editor.getHTML();
    // Isi yang dimuat dari basis data memakai format baris baru, jadi perlu diubah ke HTML agar bisa ditampilkan editor
    const newContentHtml = entry.content ? newlinesToHtml(entry.content, true) : "";

    // Hanya perbarui bila isinya benar-benar berbeda (mencegah pembaruan berulang)
    if (currentEditorContent !== newContentHtml) {
      isSettingContentRef.current = true;
      // Memakai queueMicrotask agar setContent tertunda ke mikrotugas, mencegah pemanggilan flushSync dalam siklus render React
      queueMicrotask(() => {
        editor.commands.setContent(newContentHtml, {
          emitUpdate: false,
          parseOptions: {
            preserveWhitespace: "full",
          },
        });
        // Memakai setTimeout agar onUpdate tidak langsung terpicu, sekaligus memperbarui state
        setTimeout(() => {
          isSettingContentRef.current = false;
          lastSyncedEntryRef.current = { id: entry.id, content: entry.content };
          // Memperbarui status penyimpanan (menyimpan format HTML untuk pembanding, karena editor memakai HTML secara internal)
          lastSavedContentRef.current = newContentHtml;
          // Menghitung ulang jumlah token
          if (editor) {
            const text = editor.getText({ blockSeparator: "\n" });
            setTokenCount(countTokens(text));
          }
        }, 0);
      });
    }
  }, [entry.id, entry.content, editor]);

  // Pintasan Ctrl+S untuk menyimpan
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Memeriksa apakah Ctrl+S (Windows/Linux) atau Cmd+S (Mac)
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        saveNow();
      }
    };

    // Menambahkan pendengar peristiwa papan tombol
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [saveNow]);

  return (
    <div className="prompt-editor-shell">
      {/* Area formulir - tinggi tetap, tidak menggulir */}
      <div className="prompt-editor-form">
        {/* Baris pertama: pilihan peran + nama entri */}
        <Flex
          align="center"
          gap="4"
          mb="4"
        >
          {/* Pilihan peran */}
          <LabeledSelect
            value={entry.role}
            options={roleOptions}
            onChange={(value) => {
              immediateUpdate({ role: value as "system" | "user" | "assistant" });
            }}
            size="2"
            layout="horizontal"
            gap="2"
            triggerStyle={isMobile ? {} : { minWidth: "150px" }}
            triggerLabelVisible={!isMobile}
          />

          <Separator orientation="vertical" />

          {/* Nama entri */}
          <Flex
            align="center"
            gap="2"
            className="prompt-editor-entry-name-row"
          >
            <TextField.Root
              value={entry.name}
              onChange={(e) => {
                immediateUpdate({ name: e.target.value });
              }}
              placeholder={t("promptChains.entryNameInputPlaceholder")}
              size="2"
              className="prompt-editor-entry-name-input"
            />
          </Flex>
        </Flex>
      </div>

      <div className="prompt-editor-main">
        {/* Blok editor (bergaris tepi) - area yang bisa digulir, mengisi ruang sisa */}
        <div className="prompt-editor-frame">
          {/* Area isi editor - bisa digulir */}
          <div
            ref={editorContentRef}
            className="prompt-editor-scroll-area"
          >
            <EditorContent editor={editor} />
          </div>
        </div>

        {/* Menu klik kanan */}
        <ContextMenu
          editor={editor}
          containerRef={editorContentRef}
        />
      </div>

      {/* Bilah status bawah - tetap */}
      <div className="prompt-editor-statusbar">
        <Flex
          justify="between"
          align="center"
        >
          {/* Kiri: jumlah Token */}
          <Text
            size="2"
            color="gray"
          >
            {t("promptChains.tokenCount")}: {tokenCount}
          </Text>

          {/* Kanan: status sinkronisasi salinan kerja */}
          <Text
            size="2"
            color="green"
            weight="regular"
          >
            {t("promptChains.saved")}
          </Text>
        </Flex>
      </div>
    </div>
  );
}
