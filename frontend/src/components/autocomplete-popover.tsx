/**
 * AutocompletePopover - panel pelengkapan otomatis serbaguna
 *
 * Dipakai untuk menampilkan daftar saran pelengkapan di dalam editor.
 * Gayanya mengacu pada panel pelengkapan VSCode.
 */

import { Box } from "@radix-ui/themes";
import { useEffect, useRef, useCallback } from "react";

import "./autocomplete-popover.css";

export interface AutocompleteItem {
  /** Label tampilan */
  label: string;
  /** Teks yang disisipkan */
  insertText: string;
  /** Deskripsi (opsional, ditampilkan di sisi kanan) */
  description?: string;
  /** Ikon (opsional) */
  icon?: React.ReactNode;
  /** Pergeseran kursor setelah penyisipan (angka negatif berarti bergerak ke kiri) */
  cursorOffset?: number;
}

export interface AutocompletePopoverProps {
  /** Daftar item pelengkapan */
  items: AutocompleteItem[];
  /** Posisi jangkar (relatif terhadap viewport) */
  anchorRect: { top: number; left: number } | null;
  /** Status terlihat */
  visible: boolean;
  /** Indeks yang sedang dipilih */
  selectedIndex: number;
  /** Callback saat sebuah item dipilih */
  onSelect: (item: AutocompleteItem, index: number) => void;
  /** Callback perubahan indeks terpilih */
  onSelectedIndexChange: (index: number) => void;
  /** Callback penutupan */
  onClose: () => void;
  /** Petunjuk yang ditampilkan saat tidak ada item tetap */
  hint?: string;
  /** Teks penyaring yang sedang diketik (dipakai untuk penyorotan) */
  filterText?: string;
}

/** Menyorot teks yang cocok */
function HighlightedLabel({ label, filterText }: { label: string; filterText?: string }) {
  if (!filterText) {
    return <span>{label}</span>;
  }

  const lowerLabel = label.toLowerCase();
  const lowerFilter = filterText.toLowerCase();
  const matchIndex = lowerLabel.indexOf(lowerFilter);

  if (matchIndex === -1) {
    return <span>{label}</span>;
  }

  const before = label.slice(0, matchIndex);
  const match = label.slice(matchIndex, matchIndex + filterText.length);
  const after = label.slice(matchIndex + filterText.length);

  return (
    <span>
      {before}
      <span className="highlight">{match}</span>
      {after}
    </span>
  );
}

export function AutocompletePopover({
  items,
  anchorRect,
  visible,
  selectedIndex,
  onSelect,
  onSelectedIndexChange,
  onClose,
  hint,
  filterText,
}: AutocompletePopoverProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Menggulir item terpilih ke area yang terlihat
  useEffect(() => {
    if (!listRef.current || items.length === 0) return;

    const selectedEl = listRef.current.children[selectedIndex] as HTMLElement;
    if (selectedEl) {
      selectedEl.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex, items.length]);

  // Penanganan peristiwa papan tombol
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!visible) return;

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          e.stopPropagation();
          if (items.length > 0) {
            onSelectedIndexChange((selectedIndex + 1) % items.length);
          }
          break;

        case "ArrowUp":
          e.preventDefault();
          e.stopPropagation();
          if (items.length > 0) {
            onSelectedIndexChange((selectedIndex - 1 + items.length) % items.length);
          }
          break;

        case "Enter":
        case "Tab":
          if (items.length > 0 && selectedIndex >= 0) {
            e.preventDefault();
            e.stopPropagation();
            onSelect(items[selectedIndex], selectedIndex);
          }
          break;

        case "Escape":
          e.preventDefault();
          e.stopPropagation();
          onClose();
          break;
      }
    },
    [visible, items, selectedIndex, onSelect, onSelectedIndexChange, onClose],
  );

  // Menambahkan/melepas pemantau papan tombol
  useEffect(() => {
    if (visible) {
      document.addEventListener("keydown", handleKeyDown, true);
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [visible, handleKeyDown]);

  if (!visible || !anchorRect) return null;

  const hasItems = items.length > 0;
  const showHint = !hasItems && hint;

  return (
    <Box
      ref={containerRef}
      className="autocomplete-popover"
      style={{
        position: "fixed",
        top: anchorRect.top,
        left: anchorRect.left,
        zIndex: 9999,
      }}
    >
      {showHint ? (
        <div className="autocomplete-hint">{hint}</div>
      ) : hasItems ? (
        <div
          ref={listRef}
          className="autocomplete-list"
        >
          {items.map((item, index) => (
            <div
              key={`${item.label}-${index}`}
              className={`autocomplete-item ${index === selectedIndex ? "selected" : ""}`}
              onClick={() => onSelect(item, index)}
              onMouseEnter={() => onSelectedIndexChange(index)}
            >
              {item.icon && <span className="autocomplete-item-icon">{item.icon}</span>}
              <span className="autocomplete-item-label">
                <HighlightedLabel
                  label={item.label}
                  filterText={filterText}
                />
              </span>
              {item.description && (
                <span className="autocomplete-item-desc">{item.description}</span>
              )}
            </div>
          ))}
        </div>
      ) : null}
    </Box>
  );
}
