# -*- coding: utf-8 -*-
"""
Modul parsing berkas TXT - deteksi bab dan pemotongan konten.

Mencocokkan judul bab berdasarkan aturan regex, mendukung berbagai format umum:
- judul bab/bagian/volume/koleksi/jilid berbahasa Tionghoa
- judul Chapter X
- angka, judul atau angka. judul
- judul yang diawali simbol khusus
"""

import re
from dataclasses import dataclass, field

from charset_normalizer import from_bytes


@dataclass
class ParsedChapter:
    """Satu bab hasil parsing."""

    title: str
    content: str
    word_count: int


@dataclass
class ParsedVolume:
    """Satu volume hasil parsing."""

    title: str
    chapters: list[ParsedChapter] = field(default_factory=list)


@dataclass
class ParseResult:
    """Hasil parsing TXT."""

    volumes: list[ParsedVolume] = field(default_factory=list)
    total_word_count: int = 0
    chapter_count: int = 0
    detected_encoding: str = "utf-8"


# Daftar aturan regex judul bab (diurutkan berdasarkan prioritas)
# Mengacu pada txtTocRule.json dari pembaca legado
TOC_RULES: list[tuple[str, re.Pattern[str]]] = [
    # Daftar isi (tanpa spasi) - judul bab/bagian/volume/koleksi
    # (memakai awal baris + spasi opsional sebagai pengganti lookbehind)
    (
        "daftar-isi-tanpa-spasi",
        re.compile(
            r"^[\s\u3000]+(?:\u5e8f\u7ae0|\u6954\u5b50|\u6b63\u6587(?!\u5b8c|\u7ed3)|\u7ec8\u7ae0|\u540e\u8bb0|\u5c3e\u58f0|\u756a\u5916|"
            r"\u7b2c\s{0,4}[\d\u3007\u96f6\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07\u58f9\u8d30\u53c1\u8086\u4f0d\u9646\u67d2\u634c\u7396\u62fe\u4f70\u4edf]+?\s{0,4}"
            r"(?:\u7ae0|\u8282(?!\u8bfe)|\u5377|\u96c6(?![\u5408\u548c]))).{0,30}$",
            re.MULTILINE,
        ),
    ),
    # Daftar isi - format standar
    (
        "daftar-isi",
        re.compile(
            r"^[ \u3000\t]{0,4}(?:\u5e8f\u7ae0|\u6954\u5b50|\u6b63\u6587(?!\u5b8c|\u7ed3)|\u7ec8\u7ae0|\u540e\u8bb0|\u5c3e\u58f0|\u756a\u5916|"
            r"\u7b2c\s{0,4}[\d\u3007\u96f6\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07\u58f9\u8d30\u53c1\u8086\u4f0d\u9646\u67d2\u634c\u7396\u62fe\u4f70\u4edf]+?\s{0,4}"
            r"(?:\u7ae0|\u8282(?!\u8bfe)|\u5377|\u96c6(?![\u5408\u548c])|\u90e8(?![\u5206\u8d5b\u6e38])|\u7bc7(?!\u5f20))).{0,30}$",
            re.MULTILINE,
        ),
    ),
    # angka pemisah nama judul
    (
        "angka-pemisah-judul",
        re.compile(
            r"^[ \u3000\t]{0,4}\d{1,5}[:\uff1a,.\uff0c \u3001_\u2014\-].{1,30}$",
            re.MULTILINE,
        ),
    ),
    # angka kapital pemisah nama judul
    (
        "angka-kapital-pemisah-judul",
        re.compile(
            r"^[ \u3000\t]{0,4}(?:\u5e8f\u7ae0|\u6954\u5b50|\u6b63\u6587(?!\u5b8c|\u7ed3)|\u7ec8\u7ae0|\u540e\u8bb0|\u5c3e\u58f0|\u756a\u5916|"
            r"[\u96f6\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07\u58f9\u8d30\u53c1\u8086\u4f0d\u9646\u67d2\u634c\u7396\u62fe\u4f70\u4edf]{1,8}\u7ae0?)[ \u3001_\u2014\-].{1,30}$",
            re.MULTILINE,
        ),
    ),
    # judul/nomor isi utama
    (
        "judul-isi-utama",
        re.compile(
            r"^[ \u3000\t]{0,4}\u6b63\u6587[ \u3000]{1,4}.{0,20}$",
            re.MULTILINE,
        ),
    ),
    # Chapter/Section/Part/Episode nomor judul
    (
        "Chapter/Section",
        re.compile(
            r"^[ \u3000\t]{0,4}(?:[Cc]hapter|[Ss]ection|[Pp]art|\uff30\uff21\uff32\uff34|[Nn][oO][.\u3001]|[Ee]pisode|"
            r"(?:\u5185\u5bb9|\u6587\u7ae0)?\u7b80\u4ecb|\u6587\u6848|\u524d\u8a00|\u5e8f\u7ae0|\u6954\u5b50|\u6b63\u6587(?!\u5b8c|\u7ed3)|\u7ec8\u7ae0|\u540e\u8bb0|\u5c3e\u58f0|\u756a\u5916)"
            r"\s{0,4}\d{1,4}.{0,30}$",
            re.MULTILINE,
        ),
    ),
    # simbol khusus nomor judul (memakai pencocokan awal baris sebagai pengganti lookbehind)
    (
        "simbol-khusus-nomor-judul",
        re.compile(
            r"^[\s\u3000]*[\u3010\u3014\u3016\u300c\u300e\u3008\uff3b\[](?:\u7b2c|[Cc]hapter)"
            r"[\d\u96f6\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07\u58f9\u8d30\u53c1\u8086\u4f0d\u9646\u67d2\u634c\u7396\u62fe\u4f70\u4edf]{1,10}[\u7ae0\u8282].{0,20}$",
            re.MULTILINE,
        ),
    ),
    # simbol khusus judul (tunggal) - format umum Jinjiang
    # (memakai pencocokan awal baris sebagai pengganti lookbehind)
    (
        "simbol-khusus-judul",
        re.compile(
            r"^[\s\u3000]*(?:[\u2606\u2605\u2726\u2727].{1,30}|"
            r"(?:\u5185\u5bb9|\u6587\u7ae0)?\u7b80\u4ecb|\u6587\u6848|\u524d\u8a00|\u5e8f\u7ae0|\u6954\u5b50|\u6b63\u6587(?!\u5b8c|\u7ed3)|\u7ec8\u7ae0|\u540e\u8bb0|\u5c3e\u58f0|\u756a\u5916)[ \u3000]{0,4}$",
            re.MULTILINE,
        ),
    ),
    # bab/volume nomor judul
    (
        "bab-volume-nomor-judul",
        re.compile(
            r"^[ \t\u3000]{0,4}(?:(?:\u5185\u5bb9|\u6587\u7ae0)?\u7b80\u4ecb|\u6587\u6848|\u524d\u8a00|\u5e8f\u7ae0|\u6954\u5b50|\u6b63\u6587(?!\u5b8c|\u7ed3)|\u7ec8\u7ae0|\u540e\u8bb0|\u5c3e\u58f0|\u756a\u5916|"
            r"[\u5377\u7ae0][\d\u96f6\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07\u58f9\u8d30\u53c1\u8086\u4f0d\u9646\u67d2\u634c\u7396\u62fe\u4f70\u4edf]{1,8})[ \u3000]{0,4}.{0,30}$",
            re.MULTILINE,
        ),
    ),
    # nama buku tanda kurung nomor
    (
        "nama-buku-kurung-nomor",
        re.compile(
            r"^[\u4e00-\u9fa5]{1,20}[ \u3000\t]{0,4}[(\uff08]"
            r"[\d\u3007\u96f6\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07\u58f9\u8d30\u53c1\u8086\u4f0d\u9646\u67d2\u634c\u7396\u62fe\u4f70\u4edf]{1,8}[)\uff09][ \u3000\t]{0,4}$",
            re.MULTILINE,
        ),
    ),
    # nama buku nomor
    (
        "nama-buku-nomor",
        re.compile(
            r"^[\u4e00-\u9fa5]{1,20}[ \u3000\t]{0,4}"
            r"[\d\u3007\u96f6\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07\u58f9\u8d30\u53c1\u8086\u4f0d\u9646\u67d2\u634c\u7396\u62fe\u4f70\u4edf]{1,8}[ \u3000\t]{0,4}$",
            re.MULTILINE,
        ),
    ),
]

VOLUME_TITLE_PATTERN = re.compile(
    r"^[ \t\u3000]{0,4}(?:\u7b2c\s{0,4}[\d\u3007\u96f6\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07\u58f9\u8d30\u53c1\u8086\u4f0d\u9646\u67d2\u634c\u7396\u62fe\u4f70\u4edf]+?"
    r"\s{0,4}\u5377|\u5377[\d\u3007\u96f6\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07\u58f9\u8d30\u53c1\u8086\u4f0d\u9646\u67d2\u634c\u7396\u62fe\u4f70\u4edf]{1,8}).{0,30}$",
    re.MULTILINE,
)


def _detect_encoding(content: bytes) -> str:
    """
    Mendeteksi encoding berkas.

    Args:
        content: konten bita berkas.

    Returns:
        Nama encoding yang terdeteksi, default utf-8.
    """
    match = from_bytes(content).best()
    if match is None or match.encoding is None:
        return "utf-8"

    encoding = match.encoding.lower().replace("_", "-")
    if encoding in ("gb2312", "gbk", "gb18030"):
        return "gb18030"  # Pakai gb18030 yang kompatibilitasnya paling baik

    return encoding


def decode_text_content(content: bytes) -> tuple[str, str]:
    """Mendekode konten teks dan menormalkan karakter baris baru."""
    if not content:
        return "", "utf-8"

    encoding = _detect_encoding(content)
    try:
        text = content.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        text = content.decode("utf-8", errors="ignore")
        encoding = "utf-8"

    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n"), encoding


def _count_words(text: str) -> int:
    """
    Menghitung jumlah kata Tionghoa.

    Aturan hitung: karakter Tionghoa dihitung per karakter, kata Inggris per kata.

    Args:
        text: konten teks.

    Returns:
        Jumlah kata.
    """
    # Hapus karakter spasi
    text = text.strip()
    if not text:
        return 0

    # Hitung jumlah karakter Tionghoa
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))

    # Hitung jumlah kata Inggris
    english_words = len(re.findall(r"[a-zA-Z]+", text))

    # Hitung angka
    numbers = len(re.findall(r"\d+", text))

    return chinese_chars + english_words + numbers


def _create_fallback_chapter(content: str) -> ParsedChapter | None:
    """Mengembalikan teks tak terdeteksi menjadi satu bab memakai baris pertama sebagai judul."""
    content = content.strip()
    if not content:
        return None

    lines = content.split("\n", 1)
    title = lines[0].strip() if len(lines[0].strip()) <= 50 else "\u6b63\u6587"
    chapter_content = (
        lines[1].strip() if title != "\u6b63\u6587" and len(lines) > 1 else content
    )

    return ParsedChapter(
        title=title or "\u6b63\u6587",
        content=re.sub(r"^[\n\s]+", "\u3000\u3000", chapter_content),
        word_count=_count_words(chapter_content),
    )


# Fungsi _text_to_html sudah dihapus
# Sekarang disimpan ke basis data langsung dalam format baris baru, tidak lagi
# dikonversi ke HTML


def _select_best_toc_rule(text: str) -> re.Pattern[str] | None:
    """
    Memilih aturan daftar isi terbaik.

    Menguji setiap aturan pada bagian awal teks, lalu memilih aturan dengan jumlah
    kecocokan terbanyak.

    Args:
        text: konten teks berkas.

    Returns:
        Ekspresi regex dengan kecocokan terbaik, atau None jika tidak ada yang cocok.
    """
    # Ambil 512KB konten pertama untuk menguji aturan
    sample_text = text[:512000]

    best_pattern: re.Pattern[str] | None = None
    max_matches = 0

    for _rule_name, pattern in TOC_RULES:
        # Buang kecocokan yang jaraknya terlalu dekat (menghindari salah cocok)
        valid_matches = 0
        last_pos = -1000
        for match in pattern.finditer(sample_text):
            if match.start() - last_pos > 500:  # Jarak antarbab minimal 500 karakter
                valid_matches += 1
                last_pos = match.end()

        if valid_matches > max_matches:
            max_matches = valid_matches
            best_pattern = pattern

    # Minimal 2 kecocokan baru dianggap aturan bab ditemukan
    if max_matches >= 2:
        return best_pattern

    return None


def parse_txt_content(content: bytes) -> ParseResult:
    """
    Memparsing konten berkas TXT.

    Args:
        content: konten bita berkas TXT.

    Returns:
        Hasil parsing ParseResult.
    """
    if not content:
        return ParseResult()

    # Deteksi encoding dan normalkan karakter baris baru
    text, encoding = decode_text_content(content)

    # Pilih aturan daftar isi terbaik
    toc_pattern = _select_best_toc_rule(text)

    volumes: list[ParsedVolume] = []
    default_volume: ParsedVolume | None = None

    def get_default_volume() -> ParsedVolume:
        nonlocal default_volume
        if default_volume is None:
            default_volume = ParsedVolume(title="\u7b2c\u4e00\u5377")
            volumes.append(default_volume)
        return default_volume

    toc_matches = list(toc_pattern.finditer(text)) if toc_pattern else []
    volume_matches = list(VOLUME_TITLE_PATTERN.finditer(text))
    toc_matches = [
        match
        for match in toc_matches
        if not any(
            match.start() < volume_match.end() and volume_match.start() < match.end()
            for volume_match in volume_matches
        )
    ]
    matches = sorted(
        [
            *[(match, False) for match in toc_matches],
            *[(match, True) for match in volume_matches],
        ],
        key=lambda item: item[0].start(),
    )

    if not matches:
        # Tidak ada bab terdeteksi, seluruh konten dijadikan satu bab
        content_stripped = text.strip()
        if content_stripped:
            word_count = _count_words(content_stripped)
            # Coba ambil judul dari baris pertama
            lines = content_stripped.split("\n", 1)
            if len(lines) >= 1 and len(lines[0].strip()) <= 50:
                title = lines[0].strip() or "\u6b63\u6587"
                chapter_content = lines[1].strip() if len(lines) > 1 else ""
            else:
                title = "\u6b63\u6587"
                chapter_content = content_stripped

            get_default_volume().chapters.append(
                ParsedChapter(
                    title=title,
                    content=chapter_content,  # Pakai format baris baru langsung, tidak dikonversi ke HTML
                    word_count=word_count,
                )
            )
    else:
        # Tangani konten sebelum judul daftar isi pertama (mungkin prakata/ringkasan)
        first_match_start = matches[0][0].start()
        if first_match_start > 100:  # Jadi prakata hanya jika konten awal lebih dari 100 karakter
            preface_content = text[:first_match_start].strip()
            if preface_content:
                word_count = _count_words(preface_content)
                if word_count > 50:  # Prakata minimal 50 kata
                    get_default_volume().chapters.append(
                        ParsedChapter(
                            title="\u524d\u8a00",
                            content=preface_content,  # Pakai format baris baru langsung, tidak dikonversi ke HTML
                            word_count=word_count,
                        )
                    )

        current_volume: ParsedVolume | None = None

        # Tangani setiap judul daftar isi
        for i, (match, is_explicit_volume) in enumerate(matches):
            title = match.group().strip()

            # Ambil konten judul (dari akhir judul sampai awal judul daftar isi berikutnya)
            content_start = match.end()
            if i + 1 < len(matches):
                content_end = matches[i + 1][0].start()
            else:
                content_end = len(text)

            chapter_content = text[content_start:content_end].strip()

            if is_explicit_volume or not chapter_content:
                current_volume = ParsedVolume(title=title)
                volumes.append(current_volume)
                fallback_chapter = _create_fallback_chapter(chapter_content)
                if fallback_chapter:
                    current_volume.chapters.append(fallback_chapter)
                continue

            # Hapus judul yang terduplikasi di awal konten
            if chapter_content.startswith(title):
                chapter_content = chapter_content[len(title) :].strip()

            # Bersihkan spasi dan baris baru di awal konten
            chapter_content = re.sub(r"^[\n\s]+", "\u3000\u3000", chapter_content)

            word_count = _count_words(chapter_content)

            if current_volume is None:
                current_volume = get_default_volume()

            current_volume.chapters.append(
                ParsedChapter(
                    title=title,
                    content=chapter_content,  # Pakai format baris baru langsung, tidak dikonversi ke HTML
                    word_count=word_count,
                )
            )

    # Hitung total kata
    chapters = [chapter for volume in volumes for chapter in volume.chapters]
    total_word_count = sum(chapter.word_count for chapter in chapters)

    return ParseResult(
        volumes=volumes,
        total_word_count=total_word_count,
        chapter_count=len(chapters),
        detected_encoding=encoding,
    )
