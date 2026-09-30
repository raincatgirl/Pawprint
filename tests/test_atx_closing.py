"""The closing sequence of an ATX heading is not part of its text.

CommonMark lets an author write ``# Getting Started #``. The trailing run of
``#`` is an optional closing sequence and is not part of the heading's content,
so the title of that page is ``Getting Started``. Reading it as part of the text
put a stray ``#`` into the page title, into the H1 of ``llms.txt``, and into
that page's own line in the index — decoration, quoted to the reader as
content.

The closing sequence only counts when it is preceded by whitespace, so
``# C#`` and ``# Hashtag #1`` keep their ``#``; those are content.
"""

from pawprint.content import Page, parse_page, plain_text, summarise


def _page(body: str) -> Page:
    return parse_page("/content/guide.md", "guide.md", body)


def test_atx_closing_sequence_is_not_part_of_the_title():
    assert _page("# Getting Started #\n\nProse.\n").title == "Getting Started"


def test_closing_sequence_may_be_longer_than_the_opening_one():
    assert _page("# API Reference ###\n\nProse.\n").title == "API Reference"


def test_closing_sequence_needs_whitespace_before_it():
    # `C#` is a language name, and `#1` is a heading that talks about hashes.
    assert _page("# C#\n\nProse.\n").title == "C#"
    assert _page("# Hashtag #1\n\nProse.\n").title == "Hashtag #1"


def test_a_bare_hash_after_a_space_is_still_a_closing_sequence():
    assert _page("# Release #\n\nProse.\n").title == "Release"


def test_opening_and_closing_sequences_of_different_kinds():
    # `~~~` does not close an ATX heading, so the tildes are content.
    assert _page("# Config ~~~~\n\nProse.\n").title == "Config ~~~~"


def test_no_closing_sequence_is_unaffected():
    assert _page("# Plain Title\n\nProse.\n").title == "Plain Title"


def test_an_opening_run_over_six_hashes_is_not_a_heading():
    # Seven `#` with no space is a paragraph, not a heading, so there is no
    # title to strip and the filename is the fallback.
    assert _page("####### Not a heading\n\nProse.\n").title == "guide"


def test_closing_sequence_does_not_reach_the_summary():
    # The summary is a separate path through the same reader.
    page = _page("## Setup ##\n\nInstall it with the thing.\n")
    assert page.title == "Setup"
    assert summarise(page) == "Install it with the thing."


def test_plain_text_drops_the_closing_sequence():
    # The audit counts words in the plain text, so a heading's closing hashes
    # were counted as words on their own.
    assert plain_text("## Setup ##") == "Setup"
    assert plain_text("# Release #") == "Release"


def test_plain_text_keeps_hashes_that_are_content():
    assert plain_text("## C# ###") == "C#"
    assert plain_text("## Hashtag #1 ##") == "Hashtag #1"
