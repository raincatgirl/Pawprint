"""A code fence closes its own block; no blank line is needed after it.

CommonMark treats the closing fence as a block boundary in its own right, so
the line after it opens a fresh block. ``_first_prose_paragraph`` split blocks
on blank lines alone, which meant a fence that was not followed by a blank
line had the prose underneath it glued onto the same block. The block then
started with a run of backticks, so the prose was skipped as if it were code.

The two symptoms are one bug:

- a backtick fence leaked: the page produced no summary at all, so the
  ``llms.txt`` line for that page was a bare link with no description;
- a tilde fence leaked: ``~~~`` is not in the skip prefixes, so the fence
  markers and the code between them became the summary text.

Both land in the index file an AI engine reads, so both are worth a test.
"""

from __future__ import annotations

from pawprint.content import parse_page, summarise


def test_prose_after_backtick_fence_without_blank_line_is_found():
    body = "# Install\n\n```\npip install acme\n```\nRun this once first.\n"
    page = parse_page("/x/a.md", "a.md", body)
    assert summarise(page) == "Run this once first."


def test_prose_after_fence_with_info_string_without_blank_line_is_found():
    body = "# Usage\n\n```python\nprint(1)\n```\nThe `get` method takes one argument.\n"
    page = parse_page("/x/a.md", "a.md", body)
    assert summarise(page) == "The `get` method takes one argument."


def test_tilde_fence_does_not_leak_markers_into_the_summary():
    body = "# Install\n\n~~~\npip install acme\n~~~\nRun this once first.\n"
    page = parse_page("/x/a.md", "a.md", body)
    assert summarise(page) == "Run this once first."


def test_prose_after_fence_still_found_when_blank_line_separates_them():
    # The blank-line case worked before and must keep working: the fix is not
    # "stop treating a fence as a boundary", it is "also treat the closing
    # fence as one".
    body = "# Install\n\n```\npip install acme\n```\n\nRun this once first.\n"
    page = parse_page("/x/a.md", "a.md", body)
    assert summarise(page) == "Run this once first."


def test_fence_block_with_no_prose_after_it_still_yields_nothing():
    body = "# Install\n\n```\npip install acme\n```\n"
    page = parse_page("/x/a.md", "a.md", body)
    assert summarise(page) == ""


def test_setext_underline_directly_after_a_fence_is_not_prose():
    # A fence, then a setext heading. The heading is a heading even with no
    # blank line in front of it, so it must not become the summary.
    body = "# Install\n\n```\ncode\n```\nGetting Started\n===============\n"
    page = parse_page("/x/a.md", "a.md", body)
    assert summarise(page) == ""


def test_indented_code_after_a_fence_without_blank_line_is_not_prose():
    body = "# Install\n\n```\ncode\n```\n    indented = True\n"
    page = parse_page("/x/a.md", "a.md", body)
    assert summarise(page) == ""
