"""A paragraph that begins with a punctuation mark is still a paragraph.

``_first_prose_paragraph`` decides which block of a page is prose, and it did
that by testing the block's first line against a flat tuple of single
characters: ``"#", "-", "*", "+", ">", "|", "```", "~~~", "\\t"``. Any of those
characters at the start of a line and the block was written off as structure.

CommonMark does not agree. A list item needs the marker *followed by a space*
(``- item`` is a bullet, ``--verbose`` is a word). An ATX heading needs a
hash *followed by a space* (``# Heading`` is a heading, ``#1 in a series`` is
a sentence). So a page whose prose opens with any of these was read as having
no summary at all, and its entry in ``llms.txt`` came out as a bare link with
nothing after it — the exact failure the ``--check`` work was meant to make
visible, reproduced for a class of pages nobody had to do anything wrong to
hit. Opening a sentence with ``**Note**:`` is not unusual, and neither is
starting a page with a numbered item like ``#1 in a series``.

The shared reader ``_heading_block`` already had this right, via
``_BLOCK_PREFIXES``, which spells the list markers as ``"- "``, ``"* "``,
``"+ "``. The two halves of the module had drifted apart; this pins them to
the same rule.
"""

from pawprint.content import parse_page, summarise


def _summary_of(body: str) -> str:
    return summarise(parse_page("/x/a.md", "a.md", body))


def test_emphasis_opening_paragraph_is_prose():
    assert _summary_of("**Note**: this is the only prose on the page.\n") == (
        "Note: this is the only prose on the page."
    )


def test_italic_opening_paragraph_is_prose():
    assert _summary_of("*italic* opening sentence here.\n") == "italic opening sentence here."


def test_underscore_emphasis_opening_paragraph_is_prose():
    # Not reduced to `Strong`: `__word__` is preserved on purpose, because a
    # dunder and a strong-emphasis run are indistinguishable here and a mangled
    # `__init__` is a wrong fact. The point of this case is that the paragraph
    # is found at all, rather than written off as a list.
    assert _summary_of("__Strong__ opening sentence here.\n") == (
        "__Strong__ opening sentence here."
    )


def test_dunder_opening_paragraph_is_prose():
    # A page whose prose opens with a bare dunder mention produced no summary.
    assert _summary_of("__init__ sets up the object.\n") == "__init__ sets up the object."


def test_leading_hyphen_word_is_prose():
    # `--verbose` is a flag name, not two list markers.
    assert _summary_of("--verbose is a supported flag.\n") == "--verbose is a supported flag."


def test_leading_plus_number_is_prose():
    # `+5` is a temperature, not a nested list bullet.
    assert _summary_of("+5 degrees is the service range.\n") == "+5 degrees is the service range."


def test_leading_hash_without_space_is_prose():
    # `#1` opens a numbered item; only `# Title` opens a heading.
    assert _summary_of("#1 in a series explains the format.\n") == (
        "#1 in a series explains the format."
    )


def test_real_list_is_still_skipped():
    # The fix must not swallow actual structure: a bullet is still a bullet.
    assert _summary_of("# T\n\n- item one\n- item two\n\nReal prose.\n") == "Real prose."


def test_real_atx_heading_is_still_skipped():
    assert _summary_of("# Title\n\nReal prose below.\n") == "Real prose below."


def test_nested_list_is_still_skipped():
    body = "  * nested one\n  * nested two\n\nReal prose after.\n"
    assert _summary_of(body) == "Real prose after."


def test_fence_is_still_skipped():
    body = "```\ncode here\n```\n\nReal prose after the fence.\n"
    assert _summary_of(body) == "Real prose after the fence."


def test_prose_paragraph_after_a_skipped_emphasis_line():
    # The skip is per block, not a permanent poison: a real bullet before the
    # paragraph must not stop the paragraph being found.
    body = "- a bullet\n\n**Note**: the real summary line.\n"
    assert _summary_of(body) == "Note: the real summary line."
