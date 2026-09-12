/**
 * HTML Utils
 *
 * Fungsi bantu terkait HTML.
 */

/**
 * Mengubah isi HTML menjadi format baris baru
 * Dipakai saat menyimpan ke basis data, mengubah format HTML Tiptap menjadi baris baru teks polos
 *
 * Alur pemrosesan:
 * 1. Mengganti </p> dengan karakter baris baru
 * 2. Menghapus seluruh tag HTML
 * 3. Membalik escape entitas HTML (&lt; -> <, &gt; -> >, &amp; -> &)
 *
 * @param html Isi HTML
 * @returns Isi teks polos dengan paragraf dipisah karakter baris baru
 */
export function htmlToNewlines(html: string): string {
  if (!html) return "";

  let result = html;

  // 1. Mengganti </p> dengan karakter baris baru
  result = result.replace(/<\/p\b>/gi, "\n");

  // 2. Menghapus tag <p> (termasuk yang berartribut)
  result = result.replace(/<p\b[^>]*>/gi, "");

  // 3. Menghapus seluruh tag HTML lain (misalnya <br>)
  result = result.replace(/<[^>]+>/g, "");

  // 4. Membalik escape entitas HTML
  result = decodeHtmlEntities(result);

  // 5. Menghapus karakter kosong di awal dan akhir
  result = result.trim();

  return result;
}

/**
 * Membalik escape entitas HTML menjadi karakter aslinya
 */
function decodeHtmlEntities(text: string): string {
  return text
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&"); // &amp; harus diproses paling akhir
}

/**
 * Mengubah teks berformat baris baru menjadi HTML
 * Dipakai saat memuat dari basis data, mengubah baris baru teks polos menjadi HTML yang bisa ditampilkan Tiptap
 *
 * Alur pemrosesan:
 * 1. Meng-escape teks ke bentuk HTML
 * 2. Memisahkan paragraf berdasarkan baris baru, setiap paragraf dibungkus <p></p>
 *
 * @param text Isi teks polos dengan paragraf dipisah karakter baris baru
 * @param preserveWhitespace Menentukan apakah paragraf berisi karakter kosong saja dipertahankan
 * @returns Isi HTML yang memuat tag paragraf <p></p>
 */
export function newlinesToHtml(text: string, preserveWhitespace = false): string {
  if (!text) return "";

  // Memisahkan menjadi paragraf berdasarkan baris baru (baris kosong dipertahankan)
  const paragraphs = text.split("\n");

  // Membangun HTML (paragraf kosong dipertahankan, diubah menjadi tag <p></p> kosong).
  const htmlParts: string[] = [];
  for (const p of paragraphs) {
    if (!preserveWhitespace && !p.trim()) {
      htmlParts.push("<p></p>");
    } else {
      htmlParts.push(`<p>${escapeHtml(p)}</p>`);
    }
  }

  return htmlParts.join("");
}

/**
 * Escape HTML (untuk isi teks)
 */
function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
