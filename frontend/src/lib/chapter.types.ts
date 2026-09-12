/**
 * Chapter Types
 *
 * Definisi tipe TypeScript terkait bab, sepadan dengan Schema backend.
 */

/**
 * Entitas bab (versi lengkap, menyertakan isi utama)
 */
export interface Chapter {
  id: string;
  projectId: string;
  volumeId: string;
  title: string;
  content: string;
  wordCount: number;
  order: number;
  createdAt: string;
  updatedAt: string;
}

/**
 * Item daftar bab (versi ringkas, tanpa isi utama, dipakai untuk tampilan daftar)
 */
export interface ChapterListItem {
  id: string;
  projectId: string;
  volumeId: string;
  title: string;
  wordCount: number;
  order: number;
  createdAt: string;
  updatedAt: string;
}

/**
 * Permintaan pembuatan bab
 */
export interface ChapterCreate {
  volumeId: string;
  title: string;
  content?: string;
  wordCount?: number;
}

/**
 * Permintaan pembaruan bab
 */
export interface ChapterUpdate {
  title?: string;
  content?: string;
  wordCount?: number;
}

export interface Volume {
  id: string;
  projectId: string;
  title: string;
  description: string | null;
  order: number;
  chapterCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface VolumeWithChapters extends Volume {
  chapters: ChapterListItem[];
}

export interface VolumeTreeResponse {
  volumes: VolumeWithChapters[];
  totalChapters: number;
}

export interface VolumeCreate {
  title: string;
  description?: string | null;
}

export interface VolumeUpdate {
  title?: string;
  description?: string | null;
}

export interface VolumeMove {
  newOrder: number;
}

/**
 * Permintaan pemindahan bab
 */
export interface ChapterMove {
  newOrder: number;
}

export interface ChapterMoveToVolume {
  volumeId: string;
}
