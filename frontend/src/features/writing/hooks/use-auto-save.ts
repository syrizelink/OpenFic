/**
 * Auto Save Hook
 *
 * Hook penyimpanan otomatis, mendukung penyimpanan berjadwal dan deteksi perubahan isi.
 */

import { useEffect, useState, useRef, useCallback } from "react";

interface UseAutoSaveOptions {
  /** Jeda penyimpanan (milidetik), bawaan 3 menit */
  interval?: number;
  /** Status aktif penyimpanan otomatis */
  enabled?: boolean;
  /** Fungsi penyimpanan */
  onSave: () => Promise<void>;
  /** Menandai ada perubahan yang belum tersimpan */
  hasChanges: boolean;
}

/**
 * Hook penyimpanan otomatis
 *
 * @param options Opsi konfigurasi
 * @returns Status penyimpanan dan fungsi untuk memicu penyimpanan manual
 */
export function useAutoSave({
  interval = 3 * 60 * 1000, // 3 menit
  enabled = true,
  onSave,
  hasChanges,
}: UseAutoSaveOptions) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [lastSaveTime, setLastSaveTime] = useState<number | null>(null);
  const isSavingRef = useRef(false);

  // Membersihkan pewaktu
  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // Menjalankan penyimpanan
  const save = useCallback(async () => {
    if (isSavingRef.current || !hasChanges) return;

    isSavingRef.current = true;
    try {
      await onSave();
      setLastSaveTime(Date.now());
    } finally {
      isSavingRef.current = false;
    }
  }, [onSave, hasChanges]);

  // Mereset pewaktu
  const resetTimer = useCallback(() => {
    clearTimer();
    if (enabled && hasChanges) {
      timerRef.current = setTimeout(() => {
        save();
      }, interval);
    }
  }, [clearTimer, enabled, hasChanges, interval, save]);

  // Mereset pewaktu saat isi berubah
  useEffect(() => {
    resetTimer();
    return clearTimer;
  }, [resetTimer, clearTimer]);

  useEffect(() => {
    if (lastSaveTime !== null) resetTimer();
  }, [lastSaveTime, resetTimer]);

  // Menyimpan sebelum halaman ditinggalkan
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasChanges) {
        e.preventDefault();
        // Peramban modern mengabaikan pesan kustom, tetapi returnValue tetap harus disetel
        e.returnValue = "";
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [hasChanges]);

  return {
    save,
    resetTimer,
    lastSaveTime,
  };
}
