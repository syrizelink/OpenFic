/**
 * useScrollbarAutoHide Hook
 *
 * Hook untuk menyembunyikan bilah gulir secara otomatis.
 * - Bilah gulir tampil saat pengguna menggulir dengan roda tetikus, lalu disembunyikan otomatis setelah 5 detik
 * - Bilah gulir tampil saat kursor berada di area bilah gulir (zona aktif sisi kanan)
 * - Gulir akibat perubahan isi saat mengetik tidak memicu tampilan
 */

import { useCallback, useRef, useEffect } from "react";

const SCROLLBAR_WIDTH = 20; // Lebar zona aktif bilah gulir (menyertakan sedikit kelonggaran)

/**
 * Mengembalikan objek yang memuat:
 * - containerRef: ref yang perlu dikaitkan ke wadah gulir
 * - scrollbarProps: fungsi penanganan peristiwa dan className yang perlu dikaitkan ke wadah gulir
 */
export function useScrollbarAutoHide(hideDelay = 5000) {
  const containerRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isHoveringScrollbarRef = useRef(false);

  const showScrollbar = useCallback(() => {
    if (containerRef.current) {
      containerRef.current.classList.add("scrolling");
    }
  }, []);

  const hideScrollbar = useCallback(() => {
    // Tidak disembunyikan bila kursor sedang berada di area bilah gulir
    if (isHoveringScrollbarRef.current) return;
    if (containerRef.current) {
      containerRef.current.classList.remove("scrolling");
    }
  }, []);

  const resetTimer = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    showScrollbar();
    timeoutRef.current = setTimeout(hideScrollbar, hideDelay);
  }, [showScrollbar, hideScrollbar, hideDelay]);

  // Peristiwa roda tetikus (gulir aktif oleh pengguna)
  const handleWheel = useCallback(() => {
    resetTimer();
  }, [resetTimer]);

  // Peristiwa gerak tetikus - mendeteksi keberadaan di zona aktif bilah gulir sisi kanan
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const isInScrollbarZone = e.clientX >= rect.right - SCROLLBAR_WIDTH;

      if (isInScrollbarZone && !isHoveringScrollbarRef.current) {
        isHoveringScrollbarRef.current = true;
        showScrollbar();
        // Membersihkan pewaktu penyembunyian otomatis
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
          timeoutRef.current = null;
        }
      } else if (!isInScrollbarZone && isHoveringScrollbarRef.current) {
        isHoveringScrollbarRef.current = false;
        // Memulai pewaktu penyembunyian setelah keluar dari zona aktif
        timeoutRef.current = setTimeout(hideScrollbar, hideDelay);
      }
    },
    [showScrollbar, hideScrollbar, hideDelay],
  );

  // Tetikus meninggalkan wadah
  const handleMouseLeave = useCallback(() => {
    isHoveringScrollbarRef.current = false;
    timeoutRef.current = setTimeout(hideScrollbar, hideDelay);
  }, [hideScrollbar, hideDelay]);

  // Membersihkan pewaktu
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return {
    containerRef,
    scrollbarProps: {
      className: "scrollbar-auto-hide",
      onWheel: handleWheel,
      onMouseMove: handleMouseMove,
      onMouseLeave: handleMouseLeave,
    },
  };
}
