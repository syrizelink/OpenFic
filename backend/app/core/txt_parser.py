# -*- coding: utf-8 -*-
"""
TXT 文件解析模块 - 章节识别和内容切分。

基于正则规则匹配章节标题，支持多种常见格式：
- 第X章/节/卷/集/部/篇 标题
- Chapter X 标题
- 数字、标题 或 数字. 标题
- 特殊符号开头的标题
"""

import re
from dataclasses import dataclass, field

from charset_normalizer import from_bytes


@dataclass
class ParsedChapter:
    """解析后的单个章节。"""

    title: str
    content: str
    word_count: int


@dataclass
class ParsedVolume:
    """解析后的单个卷。"""

    title: str
    chapters: list[ParsedChapter] = field(default_factory=list)


@dataclass
class ParseResult:
    """TXT 解析结果。"""

    volumes: list[ParsedVolume] = field(default_factory=list)
    total_word_count: int = 0
    chapter_count: int = 0
    detected_encoding: str = "utf-8"


# 章节标题正则规则列表（按优先级排序）
# 参考 legado 阅读器的 txtTocRule.json
TOC_RULES: list[tuple[str, re.Pattern[str]]] = [
    # 目录(去空白) - 第X章/节/卷/集 标题（使用行首 + 可选空白替代 lookbehind）
    (
        "目录(去空白)",
        re.compile(
            r"^[\s　]+(?:序章|楔子|正文(?!完|结)|终章|后记|尾声|番外|"
            r"第\s{0,4}[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]+?\s{0,4}"
            r"(?:章|节(?!课)|卷|集(?![合和]))).{0,30}$",
            re.MULTILINE,
        ),
    ),
    # 目录 - 标准格式
    (
        "目录",
        re.compile(
            r"^[ 　\t]{0,4}(?:序章|楔子|正文(?!完|结)|终章|后记|尾声|番外|"
            r"第\s{0,4}[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]+?\s{0,4}"
            r"(?:章|节(?!课)|卷|集(?![合和])|部(?![分赛游])|篇(?!张))).{0,30}$",
            re.MULTILINE,
        ),
    ),
    # 数字 分隔符 标题名称
    (
        "数字 分隔符 标题",
        re.compile(
            r"^[ 　\t]{0,4}\d{1,5}[:：,.， 、_—\-].{1,30}$",
            re.MULTILINE,
        ),
    ),
    # 大写数字 分隔符 标题名称
    (
        "大写数字 分隔符 标题",
        re.compile(
            r"^[ 　\t]{0,4}(?:序章|楔子|正文(?!完|结)|终章|后记|尾声|番外|"
            r"[零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,8}章?)[ 、_—\-].{1,30}$",
            re.MULTILINE,
        ),
    ),
    # 正文 标题/序号
    (
        "正文 标题",
        re.compile(
            r"^[ 　\t]{0,4}正文[ 　]{1,4}.{0,20}$",
            re.MULTILINE,
        ),
    ),
    # Chapter/Section/Part/Episode 序号 标题
    (
        "Chapter/Section",
        re.compile(
            r"^[ 　\t]{0,4}(?:[Cc]hapter|[Ss]ection|[Pp]art|ＰＡＲＴ|[Nn][oO][.、]|[Ee]pisode|"
            r"(?:内容|文章)?简介|文案|前言|序章|楔子|正文(?!完|结)|终章|后记|尾声|番外)"
            r"\s{0,4}\d{1,4}.{0,30}$",
            re.MULTILINE,
        ),
    ),
    # 特殊符号 序号 标题（使用行首匹配替代 lookbehind）
    (
        "特殊符号 序号 标题",
        re.compile(
            r"^[\s　]*[【〔〖「『〈［\[](?:第|[Cc]hapter)"
            r"[\d零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,10}[章节].{0,20}$",
            re.MULTILINE,
        ),
    ),
    # 特殊符号 标题(单个) - 晋江常见格式（使用行首匹配替代 lookbehind）
    (
        "特殊符号 标题",
        re.compile(
            r"^[\s　]*(?:[☆★✦✧].{1,30}|"
            r"(?:内容|文章)?简介|文案|前言|序章|楔子|正文(?!完|结)|终章|后记|尾声|番外)[ 　]{0,4}$",
            re.MULTILINE,
        ),
    ),
    # 章/卷 序号 标题
    (
        "章/卷 序号 标题",
        re.compile(
            r"^[ \t　]{0,4}(?:(?:内容|文章)?简介|文案|前言|序章|楔子|正文(?!完|结)|终章|后记|尾声|番外|"
            r"[卷章][\d零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,8})[ 　]{0,4}.{0,30}$",
            re.MULTILINE,
        ),
    ),
    # 书名 括号 序号
    (
        "书名 括号 序号",
        re.compile(
            r"^[一-龥]{1,20}[ 　\t]{0,4}[(（]"
            r"[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,8}[)）][ 　\t]{0,4}$",
            re.MULTILINE,
        ),
    ),
    # 书名 序号
    (
        "书名 序号",
        re.compile(
            r"^[一-龥]{1,20}[ 　\t]{0,4}"
            r"[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,8}[ 　\t]{0,4}$",
            re.MULTILINE,
        ),
    ),
]

VOLUME_TITLE_PATTERN = re.compile(
    r"^[ \t　]{0,4}(?:第\s{0,4}[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]+?"
    r"\s{0,4}卷|卷[\d〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]{1,8}).{0,30}$",
    re.MULTILINE,
)


def _detect_encoding(content: bytes) -> str:
    """
    检测文件编码。

    Args:
        content: 文件字节内容。

    Returns:
        检测到的编码名称，默认 utf-8。
    """
    match = from_bytes(content).best()
    if match is None or match.encoding is None:
        return "utf-8"

    encoding = match.encoding.lower().replace("_", "-")
    if encoding in ("gb2312", "gbk", "gb18030"):
        return "gb18030"  # 使用兼容性最好的 gb18030

    return encoding


def decode_text_content(content: bytes) -> tuple[str, str]:
    """解码文本内容并标准化换行符。"""
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
    统计中文字数。

    统计规则：中文字符按字计数，英文单词按词计数。

    Args:
        text: 文本内容。

    Returns:
        字数。
    """
    # 移除空白字符
    text = text.strip()
    if not text:
        return 0

    # 统计中文字符数
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))

    # 统计英文单词数
    english_words = len(re.findall(r"[a-zA-Z]+", text))

    # 统计数字
    numbers = len(re.findall(r"\d+", text))

    return chinese_chars + english_words + numbers


def _create_fallback_chapter(content: str) -> ParsedChapter | None:
    """将未识别的文本按首行标题回退为单个章节。"""
    content = content.strip()
    if not content:
        return None

    lines = content.split("\n", 1)
    title = lines[0].strip() if len(lines[0].strip()) <= 50 else "正文"
    chapter_content = (
        lines[1].strip() if title != "正文" and len(lines) > 1 else content
    )

    return ParsedChapter(
        title=title or "正文",
        content=re.sub(r"^[\n\s]+", "　　", chapter_content),
        word_count=_count_words(chapter_content),
    )


# _text_to_html 函数已移除
# 现在直接使用换行符格式保存到数据库，不再转换为 HTML


def _select_best_toc_rule(text: str) -> re.Pattern[str] | None:
    """
    选择最佳的目录规则。

    通过在文本开头部分测试每个规则，选择匹配数量最多的规则。

    Args:
        text: 文件文本内容。

    Returns:
        最佳匹配的正则表达式，如果没有匹配则返回 None。
    """
    # 取前 512KB 内容进行规则测试
    sample_text = text[:512000]

    best_pattern: re.Pattern[str] | None = None
    max_matches = 0

    for _rule_name, pattern in TOC_RULES:
        # 过滤掉间隔太近的匹配（避免误匹配）
        valid_matches = 0
        last_pos = -1000
        for match in pattern.finditer(sample_text):
            if match.start() - last_pos > 500:  # 章节间隔至少 500 字符
                valid_matches += 1
                last_pos = match.end()

        if valid_matches > max_matches:
            max_matches = valid_matches
            best_pattern = pattern

    # 至少需要 2 个匹配才认为找到了章节规则
    if max_matches >= 2:
        return best_pattern

    return None


def parse_txt_content(content: bytes) -> ParseResult:
    """
    解析 TXT 文件内容。

    Args:
        content: TXT 文件的字节内容。

    Returns:
        ParseResult 解析结果。
    """
    if not content:
        return ParseResult()

    # 检测编码并标准化换行符
    text, encoding = decode_text_content(content)

    # 选择最佳目录规则
    toc_pattern = _select_best_toc_rule(text)

    volumes: list[ParsedVolume] = []
    default_volume: ParsedVolume | None = None

    def get_default_volume() -> ParsedVolume:
        nonlocal default_volume
        if default_volume is None:
            default_volume = ParsedVolume(title="第一卷")
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
        # 没有识别到章节，整个内容作为一个章节
        content_stripped = text.strip()
        if content_stripped:
            word_count = _count_words(content_stripped)
            # 尝试从第一行提取标题
            lines = content_stripped.split("\n", 1)
            if len(lines) >= 1 and len(lines[0].strip()) <= 50:
                title = lines[0].strip() or "正文"
                chapter_content = lines[1].strip() if len(lines) > 1 else ""
            else:
                title = "正文"
                chapter_content = content_stripped

            get_default_volume().chapters.append(
                ParsedChapter(
                    title=title,
                    content=chapter_content,  # 直接使用换行符格式，不转换为 HTML
                    word_count=word_count,
                )
            )
    else:
        # 处理第一个目录标题之前的内容（可能是序言/简介）
        first_match_start = matches[0][0].start()
        if first_match_start > 100:  # 前面内容超过 100 字符才作为序言
            preface_content = text[:first_match_start].strip()
            if preface_content:
                word_count = _count_words(preface_content)
                if word_count > 50:  # 序言至少 50 字
                    get_default_volume().chapters.append(
                        ParsedChapter(
                            title="前言",
                            content=preface_content,  # 直接使用换行符格式，不转换为 HTML
                            word_count=word_count,
                        )
                    )

        current_volume: ParsedVolume | None = None

        # 处理每个目录标题
        for i, (match, is_explicit_volume) in enumerate(matches):
            title = match.group().strip()

            # 获取标题内容（从标题结束到下一个目录标题开始）
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

            # 移除内容开头的标题重复
            if chapter_content.startswith(title):
                chapter_content = chapter_content[len(title) :].strip()

            # 清理内容开头的空白和换行
            chapter_content = re.sub(r"^[\n\s]+", "　　", chapter_content)

            word_count = _count_words(chapter_content)

            if current_volume is None:
                current_volume = get_default_volume()

            current_volume.chapters.append(
                ParsedChapter(
                    title=title,
                    content=chapter_content,  # 直接使用换行符格式，不转换为 HTML
                    word_count=word_count,
                )
            )

    # 计算总字数
    chapters = [chapter for volume in volumes for chapter in volume.chapters]
    total_word_count = sum(chapter.word_count for chapter in chapters)

    return ParseResult(
        volumes=volumes,
        total_word_count=total_word_count,
        chapter_count=len(chapters),
        detected_encoding=encoding,
    )
