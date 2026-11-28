"""Tiptap XML editing, Unicode byte offsets and concurrent CRDT convergence."""

import pytest
from pycrdt import XmlElement, XmlFragment, XmlText

from app.collaboration.document import (
    new_document,
    clone_document,
    text_of,
    replace_exact,
    restore_ranges,
)
from app.core.errors import ConflictError


def test_agent_head_and_human_tail_edits_converge():
    server = new_document("Sunny morning\nThe end")
    human, agent = clone_document(server), clone_document(server)
    tail = human.get("default", type=XmlFragment).children[1].children[0]
    tail.insert(len(tail), " and bells")
    replace_exact(agent, "Sunny morning", "Rain everywhere")
    server.apply_update(human.get_update())
    server.apply_update(agent.get_update())
    human.apply_update(server.get_update())
    assert text_of(server) == text_of(human) == "Rain everywhere\nThe end and bells"


def test_multiline_replacement_retains_unaffected_paragraphs():
    doc = new_document("  one\ntwo\nthree\n untouched  \n")
    preserved = doc.get("default", type=XmlFragment).children[3]
    replace_exact(doc, "one\ntwo\nthree", "first\nsecond")
    assert text_of(doc) == "  first\nsecond\n untouched  \n"
    assert doc.get("default", type=XmlFragment).children[2] == preserved


def test_unicode_and_literal_html_survive_binary_restart_and_edits():
    doc = new_document("甲🙂 & <tag>\n\n尾\n")
    replace_exact(doc, "甲🙂 & <tag>", "乙🚀 & <new>")
    recovered = new_document(state=doc.get_update())
    replace_exact(recovered, "尾", "新的尾🙂")
    doc.apply_update(recovered.get_update())
    assert text_of(doc) == "乙🚀 & <new>\n\n新的尾🙂\n"


def test_newline_insertion_and_deletion_keep_valid_xml():
    doc = new_document("before middle after")
    replace_exact(doc, "middle", "new\nparagraph")
    assert text_of(doc) == "before new\nparagraph after"
    replace_exact(doc, "new\nparagraph", "middle")
    assert text_of(doc) == "before middle after"


def test_stale_ambiguous_and_oversized_edits_leave_original_unchanged():
    doc = new_document("same\nsame")
    for old, new in [("missing", "x"), ("same", "x"), ("same\nsame", "x" * 100001)]:
        with pytest.raises((ConflictError, ValueError)):
            replace_exact(doc, old, new)
        assert text_of(doc) == "same\nsame"
    replace_exact(doc, "same", "different", True)
    assert text_of(doc) == "different\ndifferent"


def test_multiple_xml_text_nodes_use_utf8_offsets_correctly():
    doc = new_document("甲🙂")
    paragraph = doc.get("default", type=XmlFragment).children[0]
    paragraph.children.append(XmlText("乙🚀丙"))
    replace_exact(doc, "🙂乙🚀", "新🦊")
    assert text_of(doc) == "甲新🦊丙"


def test_unsupported_rich_content_is_rejected():
    doc = new_document()
    doc.get("default", type=XmlFragment).children[0] = XmlElement(
        "heading", contents=[XmlText("title")]
    )
    with pytest.raises(ValueError):
        text_of(doc)


def test_inverse_edit_refuses_changed_target():
    doc = new_document("user rewrote the target\nThe end")
    with pytest.raises(ConflictError):
        restore_ranges(
            doc,
            [
                {
                    "old": "Agent text",
                    "text": "old text",
                    "left": "",
                    "right": "",
                    "unique": True,
                }
            ],
        )
