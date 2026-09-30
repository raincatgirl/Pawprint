"""Tests for setext-style headings (``Title`` underlined with ``===`` or ``---``).

A setext heading is a first-class CommonMark H1/H2. The parser only ever
looked for an ATX ``#`` line, so a page written in the other perfectly legal
style was titled after its filename, and its index summary came out as the
literal underline (``Getting Started ===============``).
"""

from __future__ import annotations

from pawprint.content import PageSet, parse_page, summarise
from pawprint.render import render_index


def test_setext_h1_underlined_with_equals_is_the_title():
    text = "Getting Started\n===============\n\nInstall it with pip.\n"
    assert parse_page("/x/install.md", "install.md", text).title == "Getting Started"


def test_setext_h2_underlined_with_dashes_is_the_title():
    text = "Usage\n-----\n\nRun the command like so.\n"
    assert parse_page("/x/usage.md", "usage.md", text).title == "Usage"


def test_setext_underline_is_not_used_as_the_index_summary():
    """The summary is prose, not the title. An ATX H1 is skipped as structure;
    a setext heading has to be skipped the same way, or every setext page's
    summary comes out as its own title repeated.
    """
    text = "Getting Started\n===============\n\nInstall it with pip.\n"
    page = parse_page("/x/install.md", "install.md", text)
    assert page.title == "Getting Started"
    assert summarise(page) == "Install it with pip."


def test_setext_heading_wins_over_the_filename_fallback_in_the_index():
    text = "Getting Started\n===============\n\nInstall it with pip.\n"
    page = parse_page("/x/install.md", "install.md", text)
    index = render_index(PageSet(root="/x", pages=[page]))
    assert index.startswith("# Getting Started")
    assert "===============" not in index


def test_setext_title_wins_over_a_later_atx_h1():
    """The first heading in the document is the title, whichever style it uses."""
    text = "Real Title\n==========\n\nprose\n\n# Later Section\n"
    assert parse_page("/x/a.md", "a.md", text).title == "Real Title"


def test_atx_h1_still_wins_when_it_comes_first():
    text = "# Real Title\n\nprose\n\nSetext Later\n==============\n"
    assert parse_page("/x/a.md", "a.md", text).title == "Real Title"


def test_list_bullets_are_not_a_setext_underline():
    """``- item`` under a line is a list, not a heading underline."""
    text = "Shopping\n- milk\n- eggs\n"
    assert parse_page("/x/list.md", "list.md", text).title == "list"


def test_underline_length_does_not_matter():
    """The underline can be any length: one character is enough, and a long
    dash run under a paragraph line is still a heading, not a rule.
    """
    assert parse_page("/x/a.md", "a.md", "Foo\n=\n\nprose\n").title == "Foo"
    long_rule = "Not a rule\n------------------\n\nmore prose\n"
    assert parse_page("/x/a.md", "a.md", long_rule).title == "Not a rule"


def test_up_to_three_spaces_of_indentation_is_allowed():
    """Four spaces makes it an indented code block instead."""
    assert parse_page("/x/a.md", "a.md", "   Foo\n---\n\np\n").title == "Foo"
    assert parse_page("/x/a.md", "a.md", "Foo\n   ---\n\np\n").title == "Foo"
    # Four spaces of indent before the underline kills the heading.
    assert parse_page("/x/a.md", "a.md", "Foo\n    ---\n\np\n").title == "a"


def test_exactly_three_dashes_is_a_setext_underline():
    """Three dashes are the ambiguous case, and heading wins (CommonMark)."""
    text = "Truly A Heading\n---\n\nprose\n"
    assert parse_page("/x/a.md", "a.md", text).title == "Truly A Heading"


def test_setext_underline_allows_trailing_spaces():
    text = "Getting Started\n===   \n\nprose\n"
    assert parse_page("/x/a.md", "a.md", text).title == "Getting Started"


def test_setext_underline_must_hold_a_single_character():
    """``==-==`` is not a run of one character, so it underlines nothing."""
    text = "Not Heading\n==-==\n\nprose\n"
    assert parse_page("/x/a.md", "a.md", text).title == "a"


def test_multiline_setext_heading_joins_its_lines():
    """A heading may span lines; the title is the joined, undecorated text.

    CommonMark builds the heading content by parsing the lines together, so
    emphasis opened on one line and closed on the next is emphasis, not text
    (spec example 81 renders this as ``Foo <em>bar baz</em>``). Taking only
    the last line made the title ``baz*``.
    """
    page = parse_page("/x/a.md", "a.md", "Foo *bar\nbaz*\n====\n\nprose here\n")
    assert page.title == "Foo bar baz"
    # A heading that fits on one line is unaffected.
    assert parse_page("/x/a.md", "a.md", "Foo *bar*\n====\n\np\n").title == "Foo bar"


def test_multiline_setext_heading_is_not_the_summary_either():
    text = "Foo *bar\nbaz*\n====\n\nprose here under the heading.\n"
    assert summarise(parse_page("/x/a.md", "a.md", text)) == "prose here under the heading."


def test_setext_underline_stops_at_a_blank_line():
    """The heading is the paragraph before the underline, and no more."""
    text = "Line one\nline two\n\n=== not an underline\n\nprose\n"
    assert parse_page("/x/a.md", "a.md", text).title == "a"


def test_a_list_item_is_not_underlined_by_a_later_dash_run():
    """A bullet opens a list, so the dash line below it is not an underline."""
    text = "First item\n- second item\n-\n"
    assert parse_page("/x/a.md", "a.md", text).title == "a"


def test_setext_heading_inside_a_code_fence_is_ignored():
    text = "```\nFake Title\n=======\n```\n\nprose\n"
    assert parse_page("/x/a.md", "a.md", text).title == "a"


def test_setext_underline_after_an_atx_heading_is_a_thematic_break():
    """A heading line is not a paragraph, so it cannot be underlined."""
    text = "# Title\n---\n\nprose\n"
    assert parse_page("/x/a.md", "a.md", text).title == "Title"
