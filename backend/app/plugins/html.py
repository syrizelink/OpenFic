"""Initialize iframe applications without layout-dependent SDK script paths."""

from html import escape
from html.parser import HTMLParser


def inject_sdk(document: str, url: str) -> str:
    class Position(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.head = None
            self.script = None
            self.doctype = 0
            self.starts = [0]
            self.starts.extend(
                index + 1 for index, char in enumerate(document) if char == "\n"
            )

        def position_offset(self):
            line, column = self.getpos()
            return self.starts[line - 1] + column

        def handle_starttag(self, tag, attrs):
            if tag == "head" and self.head is None:
                self.head = self.position_offset() + len(self.get_starttag_text())
            if tag == "script" and self.script is None:
                self.script = self.position_offset()

        def handle_decl(self, decl):
            if decl.lower().startswith("doctype"):
                self.doctype = self.position_offset() + len(decl) + 3

    position = Position()
    position.feed(document)
    offset = position.head if position.head is not None else position.doctype
    if position.script is not None:
        offset = min(offset, position.script)
    script = (
        f'<script src="{escape(url, quote=True)}" crossorigin="anonymous"></script>'
    )
    return document[:offset] + script + document[offset:]
