"""Edit Tiptap paragraph XML using Yjs-compatible CRDTs inside Python."""

from pycrdt import Doc, XmlElement, XmlFragment, XmlText

from app.core.editor_content_limits import validate_editor_content
from app.core.errors import ConflictError


def new_document(content: str = "", state: bytes | None = None) -> Doc:
    document = Doc({"default": XmlFragment()})
    if state is not None:
        document.apply_update(state)
    else:
        fragment = document.get("default", type=XmlFragment)
        with document.transaction():
            for line in content.split("\n"):
                fragment.children.append(
                    XmlElement("paragraph", contents=[XmlText(line)])
                )
    text_of(document)
    return document


def clone_document(document: Doc) -> Doc:
    return new_document(state=document.get_update())


def paragraph_text(paragraph: XmlElement) -> str:
    if paragraph.tag != "paragraph" or len(paragraph.attributes):
        raise ValueError("协同章节仅支持纯文本段落")
    chunks = []
    for child in paragraph.children:
        if not isinstance(child, XmlText):
            raise ValueError("协同章节中含有不支持的节点")
        for value, attributes in child.diff():
            if not isinstance(value, str) or attributes:
                raise ValueError("协同章节仅支持纯文本")
            chunks.append(value)
    return "".join(chunks)


def text_of(document: Doc) -> str:
    paragraphs = list(document.get("default", type=XmlFragment).children)
    if not paragraphs or len(paragraphs) > 2000:
        raise ValueError("章节必须包含 1 至 2000 个段落")
    lines = []
    for paragraph in paragraphs:
        if not isinstance(paragraph, XmlElement):
            raise ValueError("章节中含有不支持的节点")
        lines.append(paragraph_text(paragraph))
    content = "\n".join(lines)
    validate_editor_content(content)
    return content


def _edit_paragraph(paragraph: XmlElement, start: int, end: int, text: str) -> None:
    """Keep text identities; convert Python codepoint offsets to pycrdt UTF-8 offsets."""
    children = list(paragraph.children)
    if not children:
        paragraph.children.append(XmlText(text))
        return
    position = 0
    target: tuple[XmlText, int] | None = None
    edits = []
    for child in children:
        if not isinstance(child, XmlText):
            raise ValueError("章节中含有不支持的节点")
        value = str(child)
        if target is None and start <= position + len(value):
            target = child, len(value[: start - position].encode("utf-8"))
        left, right = max(0, start - position), min(len(value), end - position)
        if right > left:
            edits.append(
                (
                    child,
                    len(value[:left].encode("utf-8")),
                    len(value[:right].encode("utf-8")),
                )
            )
        position += len(value)
    if target is None:
        raise ValueError("无效的章节编辑位置")
    for child, left, right in reversed(edits):
        del child[left:right]
    target[0].insert(target[1], text)


def replace_range(document: Doc, start: int, end: int, replacement: str) -> None:
    fragment = document.get("default", type=XmlFragment)
    paragraphs = list(fragment.children)

    def locate(position: int) -> tuple[int, int]:
        offset = 0
        for index, paragraph in enumerate(paragraphs):
            if not isinstance(paragraph, XmlElement):
                raise ValueError("章节中含有不支持的节点")
            length = len(paragraph_text(paragraph))
            if position <= offset + length:
                return index, position - offset
            offset += length + 1
        raise ValueError("无效的章节编辑位置")

    first_index, left = locate(start)
    last_index, right = locate(end)
    first, last = paragraphs[first_index], paragraphs[last_index]
    if not isinstance(first, XmlElement) or not isinstance(last, XmlElement):
        raise ValueError("章节中含有不支持的节点")
    lines = replacement.split("\n")
    with document.transaction():
        if first_index == last_index and len(lines) == 1:
            _edit_paragraph(first, left, right, replacement)
            return
        suffix = paragraph_text(last)[right:]
        _edit_paragraph(first, left, len(paragraph_text(first)), lines[0])
        if last_index > first_index:
            del fragment.children[first_index + 1 : last_index + 1]
        if len(lines) == 1:
            length = len(paragraph_text(first))
            _edit_paragraph(first, length, length, suffix)
        else:
            for index, line in enumerate(lines[1:], start=1):
                value = line + (suffix if index == len(lines) - 1 else "")
                fragment.children.insert(
                    first_index + index,
                    XmlElement("paragraph", contents=[XmlText(value)]),
                )


def replace_exact(document: Doc, old: str, new: str, replace_all: bool = False) -> None:
    if not old:
        raise ConflictError("old_content 不能为空")
    content = text_of(document)
    matches = []
    start = 0
    while (position := content.find(old, start)) != -1:
        matches.append(position)
        start = position + len(old)
    if not matches:
        raise ConflictError("目标文本已改变或不存在，请重新读取章节")
    if not replace_all and len(matches) != 1:
        raise ConflictError("目标文本不唯一，请提供更多上下文")
    validate_editor_content(
        content.replace(old, new) if replace_all else content.replace(old, new, 1)
    )
    for position in reversed(matches):
        replace_range(document, position, position + len(old), new)
    text_of(document)


def restore_ranges(document: Doc, edits: list[dict]) -> None:
    for edit in edits:
        content = text_of(document)
        needle = edit["left"] + edit["old"] + edit["right"]
        position = content.find(needle) if needle else -1
        start = position + len(edit["left"])
        if position < 0 or content.find(needle, position + 1) >= 0:
            needle = edit["old"]
            position = content.find(needle) if edit["unique"] and needle else -1
            start = position
        if position < 0 or content.find(needle, position + 1) >= 0:
            raise ConflictError("回滚目标已改变或不唯一，无法安全回滚")
        replace_range(document, start, start + len(edit["old"]), edit["text"])
    text_of(document)
