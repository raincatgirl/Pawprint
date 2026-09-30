"""A summary is prose, not markdown.

``llms.txt`` is the one file that is actually read by an AI engine, and every
entry is a bullet whose text is this summary. Emitting the raw markdown source
meant the index line quoted its own markup back at the reader, and a link in
the first paragraph became a *second* link nested inside the entry's own
link text — which most Markdown renderers drop on the floor.

``plain_text`` already exists and already does this conversion, for the audit's
word count. The summary was never routed through it.
"""

from __future__ import annotations

from pawprint.content import parse_page, summarise


def _summary(body: str, **kwargs) -> str:
    return summarise(parse_page("/x/a.md", "a.md", body), **kwargs)


def test_summarise_strips_emphasis():
    assert _summary("# T\n\nSome *emphasised* and **strong** prose here.\n") == (
        "Some emphasised and strong prose here."
    )


def test_summarise_strips_inline_code_ticks():
    assert _summary("# T\n\nRun the `acme init` command first.\n") == (
        "Run the acme init command first."
    )


def test_summarise_does_not_nest_a_link_inside_the_entry_link():
    # This is the defect in its worst form: the index entry is
    #   - [API](/docs/api): ... see [docs](https://x.test).
    # and the inner bracket pair turns the rest of the line into a link target
    # that never renders, so the URL the page depends on is simply lost.
    out = _summary("# T\n\nSee [the guide](https://x.test/guide) for details.\n")
    assert "[the guide]" not in out
    assert "https://x.test/guide" in out
    assert "the guide (https://x.test/guide)" in out


def test_summarise_keeps_the_url_but_drops_the_image_syntax():
    assert _summary("# T\n\nA ![diagram](img/flow.png) of the flow.\n") == (
        "A diagram of the flow."
    )


def test_summarise_leaves_dunder_identifiers_intact():
    # `plain_text` already had a dunder guard, added on 2026-10-11 for exactly
    # this reason. Routing the summary through it must not undo that.
    assert "__init__" in _summary("# T\n\nThe __init__ method does the work.\n")
    assert "load_user_profile" in _summary("# T\n\nCall load_user_profile() here.\n")


def test_summarise_still_prefers_front_matter_description_verbatim():
    # A description is author-written prose and is used verbatim everywhere
    # else; it must not be run through the stripper.
    page = parse_page("/x/a.md", "a.md", "---\ndescription: Keep *this* as-is.\n---\nBody.\n")
    assert summarise(page) == "Keep *this* as-is."


def test_summarise_strips_a_leading_heading_marker_from_the_fallback_prose():
    # Guard against the stripper deleting the dash that makes the entry a
    # bullet rather than reaching inside the text.
    out = _summary("# T\n\n- a list is not the summary\n\nReal prose here.\n")
    assert out == "Real prose here."


def test_summarise_truncates_after_stripping_not_before():
    # Truncation counts characters of the *emitted* line. If the strip ran
    # after the cut, a summary could end mid-markup. The limit is on what the
    # reader sees, so stripping has to happen first.
    long_word = "x" * 200
    out = _summary(f"# T\n\nThe **{'a ' * 120}{long_word}** trailing words.\n", limit=50)
    assert "**" not in out
    assert out.endswith("...")
    assert len(out) <= 54
