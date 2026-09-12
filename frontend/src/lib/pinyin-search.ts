/**
 * Pinyin Search Utils
 *
 * Fungsi bantu pencarian pinyin, mendukung konversi aksara Han ke pinyin dan pengambilan huruf awal.
 */

import Pinyin from "tiny-pinyin";

/**
 * Mengambil pinyin lengkap sebuah teks (huruf kecil, tanpa spasi)
 */
export function getPinyin(text: string): string {
  if (!text) return "";
  return Pinyin.convertToPinyin(text, "", true);
}

/**
 * Mengambil rangkaian huruf awal pinyin
 * Contoh: \u7b2c\u4e00\u7ae0 -> dyz
 */
export function getInitials(text: string): string {
  if (!text) return "";
  const chars = text.split("");
  return chars
    .map((char) => {
      if (Pinyin.isSupported()) {
        const pinyinArr = Pinyin.parse(char);
        if (pinyinArr.length > 0 && pinyinArr[0].type === 2) {
          // type 2 menandakan aksara Han
          return pinyinArr[0].target.charAt(0).toLowerCase();
        }
      }
      // Karakter non-Han dikembalikan apa adanya (dijadikan huruf kecil bila berupa huruf)
      return char.toLowerCase();
    })
    .join("");
}

/**
 * Menghapus tag HTML, mengembalikan teks polos
 * Tag baris baru (p, br) diubah menjadi spasi agar kecocokan tidak melintasi baris
 */
export function stripHtml(html: string): string {
  if (!html) return "";
  // Mengganti tag terkait baris baru dengan spasi
  const processed = html
    .replace(/<\/p>/gi, " ")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<\/div>/gi, " ")
    .replace(/<\/li>/gi, " ");
  // Membuat elemen DOM sementara untuk mengurai sisa HTML
  const doc = new DOMParser().parseFromString(processed, "text/html");
  // Mengambil teks polos dan memadatkan spasi berlebih
  const text = doc.body.textContent || "";
  return text.replace(/\s+/g, " ").trim();
}

/**
 * Konfigurasi pencarian Fuse.js bawaan
 */
export const defaultFuseOptions = {
  includeMatches: true,
  threshold: 0.1,
  ignoreLocation: true,
  distance: 50,
  useExtendedSearch: false,
};

/**
 * Fungsi pencocokan pinyin sederhana
 * Mendukung: kecocokan teks asli, kecocokan pinyin penuh, kecocokan huruf awal
 */
export function pinyinMatch(text: string, query: string): boolean {
  if (!text || !query) return false;

  try {
    const lowerText = text.toLowerCase();
    const lowerQuery = query.toLowerCase();

    // Kecocokan teks asli
    if (lowerText.includes(lowerQuery)) {
      return true;
    }

    // Kecocokan pinyin penuh
    const pinyin = getPinyin(text);
    if (pinyin.includes(lowerQuery)) {
      return true;
    }

    // Kecocokan huruf awal
    const initials = getInitials(text);
    if (initials.includes(lowerQuery)) {
      return true;
    }

    return false;
  } catch {
    return text.toLowerCase().includes(query.toLowerCase());
  }
}
