/**
 * Agent Branding
 *
 * Daftar warna dan Icon bawaan untuk agen utama beserta fungsi bantunya.
 * Kunci warna mengacu pada warna tema Radix, kunci Icon mengacu pada ikon lucide.
 */

import type { LucideIcon } from "lucide-react";
import {
  Anchor,
  Bell,
  Blocks,
  BookOpen,
  Camera,
  Cloud,
  Compass,
  Crown,
  Feather,
  Flame,
  Gem,
  Globe,
  GraduationCap,
  Heart,
  Key,
  Lightbulb,
  ListChecks,
  Map,
  Moon,
  Music,
  Palette,
  PenTool,
  Puzzle,
  Rocket,
  Shield,
  Sparkles,
  Star,
  Target,
  Wand2,
  Zap,
} from "lucide-react";

import i18n from "@/i18n";

export interface AgentBrandingOption {
  value: string;
  labelKey: string;
}

export const AGENT_COLOR_OPTIONS: AgentBrandingOption[] = [
  { value: "blue", labelKey: "agentBranding.color.blue" },
  { value: "green", labelKey: "agentBranding.color.green" },
  { value: "orange", labelKey: "agentBranding.color.orange" },
  { value: "purple", labelKey: "agentBranding.color.purple" },
  { value: "teal", labelKey: "agentBranding.color.teal" },
  { value: "red", labelKey: "agentBranding.color.red" },
  { value: "amber", labelKey: "agentBranding.color.amber" },
  { value: "pink", labelKey: "agentBranding.color.pink" },
  { value: "indigo", labelKey: "agentBranding.color.indigo" },
  { value: "cyan", labelKey: "agentBranding.color.cyan" },
  { value: "lime", labelKey: "agentBranding.color.lime" },
  { value: "violet", labelKey: "agentBranding.color.violet" },
  { value: "bronze", labelKey: "agentBranding.color.bronze" },
  { value: "gray", labelKey: "agentBranding.color.gray" },
];

export interface AgentIconOption extends AgentBrandingOption {
  icon: LucideIcon;
}

export const AGENT_ICON_OPTIONS: AgentIconOption[] = [
  { value: "bot", labelKey: "agentBranding.icon.bot", icon: GraduationCap },
  { value: "sparkles", labelKey: "agentBranding.icon.sparkles", icon: Sparkles },
  { value: "pen-tool", labelKey: "agentBranding.icon.penTool", icon: PenTool },
  { value: "wand", labelKey: "agentBranding.icon.wand", icon: Wand2 },
  { value: "compass", labelKey: "agentBranding.icon.compass", icon: Compass },
  { value: "crown", labelKey: "agentBranding.icon.crown", icon: Crown },
  { value: "rocket", labelKey: "agentBranding.icon.rocket", icon: Rocket },
  { value: "shield", labelKey: "agentBranding.icon.shield", icon: Shield },
  { value: "star", labelKey: "agentBranding.icon.star", icon: Star },
  { value: "lightbulb", labelKey: "agentBranding.icon.lightbulb", icon: Lightbulb },
  { value: "target", labelKey: "agentBranding.icon.target", icon: Target },
  { value: "zap", labelKey: "agentBranding.icon.zap", icon: Zap },
  { value: "book-open", labelKey: "agentBranding.icon.bookOpen", icon: BookOpen },
  { value: "list-checks", labelKey: "agentBranding.icon.listChecks", icon: ListChecks },
  { value: "feather", labelKey: "agentBranding.icon.feather", icon: Feather },
  { value: "palette", labelKey: "agentBranding.icon.palette", icon: Palette },
  { value: "blocks", labelKey: "agentBranding.icon.blocks", icon: Blocks },
  { value: "gem", labelKey: "agentBranding.icon.gem", icon: Gem },
  { value: "key", labelKey: "agentBranding.icon.key", icon: Key },
  { value: "globe", labelKey: "agentBranding.icon.globe", icon: Globe },
  { value: "map", labelKey: "agentBranding.icon.map", icon: Map },
  { value: "music", labelKey: "agentBranding.icon.music", icon: Music },
  { value: "camera", labelKey: "agentBranding.icon.camera", icon: Camera },
  { value: "heart", labelKey: "agentBranding.icon.heart", icon: Heart },
  { value: "flame", labelKey: "agentBranding.icon.flame", icon: Flame },
  { value: "anchor", labelKey: "agentBranding.icon.anchor", icon: Anchor },
  { value: "bell", labelKey: "agentBranding.icon.bell", icon: Bell },
  { value: "puzzle", labelKey: "agentBranding.icon.puzzle", icon: Puzzle },
  { value: "cloud", labelKey: "agentBranding.icon.cloud", icon: Cloud },
  { value: "moon", labelKey: "agentBranding.icon.moon", icon: Moon },
];

export const DEFAULT_AGENT_COLOR = "blue";
export const DEFAULT_AGENT_ICON = "bot";

/**
 * Deskripsi bawaan setiap Agent bawaan, disalin dari
 * `backend/app/agent_runtime/agents/definitions.py`.
 *
 * Dipakai untuk mendeteksi apakah pengguna sudah menyunting deskripsi sendiri.
 * Jika deskripsi masih sama dengan bawaan, kita tampilkan versi i18n agar ikut
 * bahasa antarmuka; jika sudah disunting, deskripsi pengguna dipakai apa adanya.
 *
 * Varian historis berbahasa Tionghoa tetap dicantumkan supaya data lama yang
 * sudah tersimpan di basis data tetap dikenali sebagai deskripsi bawaan.
 * Varian tersebut ditulis dengan escape `\uXXXX` karena hanya berfungsi sebagai
 * data pembanding, bukan teks yang ditampilkan.
 */
const DEFAULT_AGENT_DESCRIPTIONS: Record<string, readonly string[]> = {
  build: [
    "Agen bawaan yang menjalankan tugas penulisan umum dan menjadwalkan sub-agen untuk menuntaskan pekerjaan bila diperlukan",
    "\u9ed8\u8ba4\u7684 Agent\uff0c\u6267\u884c\u901a\u7528\u7684\u5199\u4f5c\u4efb\u52a1\uff0c\u5e76\u5728\u9700\u8981\u65f6\u8c03\u5ea6\u5b50 Agent \u5b8c\u6210\u5de5\u4f5c",
  ],
  plan: [
    "Berfokus pada perencanaan dan koordinasi: menata pekerjaan sub-agen, menelaah, dan menyerahkan hasil untuk tugas penulisan sistematis",
    "\u4e13\u6ce8\u4e8e\u89c4\u5212\u548c\u534f\u8c03\uff0c\u7ec4\u7ec7\u5b50 Agent \u5de5\u4f5c\u3001\u5ba1\u67e5\u4e0e\u4ea4\u4ed8\uff0c\u8d1f\u8d23\u6267\u884c\u7cfb\u7edf\u5199\u4f5c\u7684\u4efb\u52a1",
  ],
  explore: [
    "Menangani pengumpulan informasi, penataan konteks, dan pencarian bukti",
    "\u8d1f\u8d23\u4fe1\u606f\u641c\u96c6\u3001\u4e0a\u4e0b\u6587\u68b3\u7406\u4e0e\u8bc1\u636e\u67e5\u627e",
  ],
  composer: [
    "Menangani perancangan alur cerita, perencanaan struktur, dan penataan rencana penulisan",
    "\u8d1f\u8d23\u5267\u60c5\u8bbe\u8ba1\u3001\u7ed3\u6784\u89c4\u5212\u4e0e\u5199\u4f5c\u65b9\u6848\u7684\u7ec4\u7ec7",
  ],
  auditor: [
    "Menelaah rencana, menghasilkan pendapat telaah, menunjukkan masalah, dan mengajukan saran perbaikan.",
    "\u8d1f\u8d23\u5ba1\u67e5\u8ba1\u5212\uff0c\u4ea7\u51fa\u8bc4\u5ba1\u610f\u89c1\u3001\u6307\u51fa\u95ee\u9898\u5e76\u63d0\u51fa\u4fee\u6b63\u5efa\u8bae\u3002",
  ],
  writer: [
    "Menangani penulisan isi bab, penulisan susulan, dan perbaikan isi utama.",
    "\u8d1f\u8d23\u7ae0\u8282\u5185\u5bb9\u64b0\u5199\u3001\u8865\u5199\u4e0e\u6b63\u6587\u4fee\u6539\u3002",
  ],
  actor: [
    "Menjalankan perbaikan sesuai tujuan yang sudah ditetapkan dan menggerakkan tindakan konkret.",
    "\u8d1f\u8d23\u6309\u65e2\u5b9a\u76ee\u6807\u6267\u884c\u4fee\u6539\u5e76\u63a8\u8fdb\u5177\u4f53\u52a8\u4f5c\u3002",
  ],
  reviewer: [
    "Menelaah isi penulisan, menghasilkan pendapat telaah, menunjukkan masalah, dan mengajukan saran perbaikan.",
    "\u8d1f\u8d23\u5ba1\u67e5\u5199\u4f5c\u5185\u5bb9\uff0c\u4ea7\u51fa\u8bc4\u5ba1\u610f\u89c1\u3001\u6307\u51fa\u95ee\u9898\u5e76\u63d0\u51fa\u4fee\u6b63\u5efa\u8bae\u3002",
  ],
};

export function getAgentDisplayDescription(key: string, description: string): string {
  const defaults = DEFAULT_AGENT_DESCRIPTIONS[key];
  if (!defaults) {
    return description;
  }
  const trimmed = description.trim();
  if (trimmed && !defaults.includes(trimmed)) {
    return description;
  }
  return i18n.t(`agentBranding.primaryDescription.${key}`);
}

export function getAgentIcon(value?: string | null): LucideIcon {
  return AGENT_ICON_OPTIONS.find((option) => option.value === value)?.icon ?? GraduationCap;
}

export function getAgentColorVar(color?: string | null): string {
  const resolved = AGENT_COLOR_OPTIONS.some((option) => option.value === color)
    ? (color as string)
    : DEFAULT_AGENT_COLOR;
  return `var(--${resolved}-9)`;
}

export function getAgentIconColor(color?: string | null): string {
  const resolved = AGENT_COLOR_OPTIONS.some((option) => option.value === color)
    ? (color as string)
    : DEFAULT_AGENT_COLOR;
  return `color-mix(in oklab, var(--${resolved}-9) 80%, var(--gray-12))`;
}
