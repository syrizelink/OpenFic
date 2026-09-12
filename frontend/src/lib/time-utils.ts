/**
 * Time Utils
 *
 * Fungsi bantu terkait waktu.
 */

import { formatDistanceToNow, differenceInMinutes, parseISO } from "date-fns";
import { zhCN, enUS, id as idID } from "date-fns/locale";

import i18n from "@/i18n";

/**
 * Mengurai string waktu ISO sekaligus menangani persoalan zona waktu
 * Jika string waktu tidak memuat informasi zona waktu, nilainya dianggap waktu UTC
 */
function parseDate(dateString: string): Date {
  // Jika informasi zona waktu tidak ada (tanpa Z atau pergeseran +/-), tambahkan Z sebagai penanda UTC
  if (!dateString.endsWith("Z") && !dateString.match(/[+-]\d{2}:\d{2}$/)) {
    return parseISO(dateString + "Z");
  }
  return parseISO(dateString);
}

/**
 * Mengambil locale date-fns sesuai bahasa saat ini
 */
function getDateLocale() {
  const language = i18n.language;
  switch (language) {
    case "id":
      return idID;
    case "zh-CN":
      return zhCN;
    case "en":
      return enUS;
    default:
      return idID;
  }
}

/**
 * Memformat waktu relatif
 * Dalam 5 menit ditampilkan sebagai "beberapa saat lalu", selain itu memakai waktu relatif
 */
export function formatRelativeTime(dateString: string): string {
  const date = parseDate(dateString);
  const now = new Date();
  const diffMinutes = differenceInMinutes(now, date);

  if (diffMinutes < 5) {
    return i18n.t("time.justNow");
  }

  return formatDistanceToNow(date, {
    addSuffix: true,
    locale: getDateLocale(),
  });
}
