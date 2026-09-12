/**
 * Thinking Parser
 *
 * Mengurai tag penalaran pada balasan AI (<think> dan <thinking>)
 */

export interface ThinkingBlock {
  /** Isi penalaran */
  content: string;
  /** Waktu mulai (relatif terhadap awal balasan) */
  startTime: number;
  /** Waktu selesai (relatif terhadap awal balasan) */
  endTime: number;
  /** Durasi penalaran (detik) */
  duration: number;
}

export interface ParsedMessage {
  /** Isi yang benar-benar ditampilkan (tanpa tag penalaran) */
  displayContent: string;
  /** Daftar blok penalaran */
  thinkingBlocks: ThinkingBlock[];
  /** Menandai penalaran sedang berjalan */
  isThinking: boolean;
}

/**
 * Mengurai tag penalaran dalam sebuah pesan
 * Mendukung dua bentuk tag: <think>...</think> dan <thinking>...</thinking>
 */
export function parseThinkingTags(content: string, currentTime: number): ParsedMessage {
  // Mencocokkan tag <think> atau <thinking>
  const thinkRegex = /<think(?:ing)?>([\s\S]*?)(?:<\/think(?:ing)?>|$)/gi;
  const thinkingBlocks: ThinkingBlock[] = [];
  let displayContent = content;
  let isThinking = false;

  // Mengambil seluruh blok penalaran
  let match;
  while ((match = thinkRegex.exec(content)) !== null) {
    const thinkContent = match[1];
    const isComplete = match[0].includes("</");

    if (isComplete) {
      // Blok penalaran yang utuh
      thinkingBlocks.push({
        content: thinkContent,
        startTime: currentTime,
        endTime: currentTime,
        duration: 0, // Akan dihitung kemudian
      });
    } else {
      // Penalaran sedang berjalan
      isThinking = true;
    }
  }

  // Menghapus tag penalaran, hanya menyisakan isi yang ditampilkan
  displayContent = content.replace(/<think(?:ing)?>([\s\S]*?)<\/think(?:ing)?>/gi, "");

  // Jika penalaran masih berjalan, tag yang belum tertutup juga dihapus
  displayContent = displayContent.replace(/<think(?:ing)?>([\s\S]*?)$/gi, "");

  return {
    displayContent: displayContent.trim(),
    thinkingBlocks,
    isThinking,
  };
}

/**
 * Mengurai tag penalaran pada isi mengalir secara langsung
 */
export class ThinkingStreamParser {
  private buffer: string = "";
  private thinkingBlocks: ThinkingBlock[] = [];
  private currentThinkingStart: number | null = null;
  private startTime: number;

  constructor() {
    this.startTime = Date.now();
  }

  /**
   * Menambahkan potongan isi baru
   */
  add(chunk: string): ParsedMessage {
    this.buffer += chunk;
    return this.parse();
  }

  /**
   * Mengambil isi penyangga saat ini
   */
  getBuffer(): string {
    return this.buffer;
  }

  /**
   * Mengurai penyangga saat ini
   */
  private parse(): ParsedMessage {
    const currentTime = (Date.now() - this.startTime) / 1000;

    // Memeriksa adanya tag penalaran yang belum tertutup
    const openThinkMatch = this.buffer.match(/<think(?:ing)?>/i);
    const closeThinkMatch = this.buffer.match(/<\/think(?:ing)?>/i);

    let isThinking = false;

    if (openThinkMatch && !closeThinkMatch) {
      // Penalaran sedang berjalan
      isThinking = true;
      if (this.currentThinkingStart === null) {
        this.currentThinkingStart = currentTime;
      }
    } else if (openThinkMatch && closeThinkMatch) {
      // Penalaran selesai
      if (this.currentThinkingStart !== null) {
        const thinkContent =
          this.buffer.match(/<think(?:ing)?>([\s\S]*?)<\/think(?:ing)?>/i)?.[1] || "";
        this.thinkingBlocks.push({
          content: thinkContent,
          startTime: this.currentThinkingStart,
          endTime: currentTime,
          duration: currentTime - this.currentThinkingStart,
        });
        this.currentThinkingStart = null;
      }
    }

    // Menghapus tag penalaran
    const displayContent = this.buffer
      .replace(/<think(?:ing)?>([\s\S]*?)<\/think(?:ing)?>/gi, "")
      .replace(/<think(?:ing)?>([\s\S]*?)$/gi, "")
      .trim();

    return {
      displayContent,
      thinkingBlocks: this.thinkingBlocks,
      isThinking,
    };
  }

  /**
   * Menyelesaikan penguraian
   */
  finish(): ParsedMessage {
    // Jika masih ada tag penalaran yang belum tertutup, tutup secara paksa
    if (this.currentThinkingStart !== null) {
      const currentTime = (Date.now() - this.startTime) / 1000;
      const thinkContent = this.buffer.match(/<think(?:ing)?>([\s\S]*?)$/i)?.[1] || "";
      this.thinkingBlocks.push({
        content: thinkContent,
        startTime: this.currentThinkingStart,
        endTime: currentTime,
        duration: currentTime - this.currentThinkingStart,
      });
      this.currentThinkingStart = null;
    }

    const displayContent = this.buffer
      .replace(/<think(?:ing)?>([\s\S]*?)<\/think(?:ing)?>/gi, "")
      .replace(/<think(?:ing)?>([\s\S]*?)$/gi, "")
      .trim();

    return {
      displayContent,
      thinkingBlocks: this.thinkingBlocks,
      isThinking: false,
    };
  }
}
