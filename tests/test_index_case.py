"""A capitalised ``Index.md`` is a landing page, the way a lowercase one is.

``_walk`` matches content suffixes with ``str.lower().endswith``, so
``Index.md`` and ``Guide.MD`` are collected as content. ``is_index_path``
compared the filename against ``index.md`` and ``index.markdown`` verbatim, so
those pages were collected and then treated as ordinary pages: ``Index.md`` was
linked at ``/Index`` rather than ``/``, and ``docs/Index.md`` at ``/docs/Index``
rather than ``/docs/``.

That is the same bug the ``index.markdown`` fix in ``_INDEX_STEMS`` addressed,
left open on the other axis. The consequences are the visible ones the earlier
fixes were about: the site gets named after a sibling page instead of its own
index, and the links in ``llms.txt`` point at URLs that would 404 on a real
site — because a static generator serving ``docs/index.md`` serves it at
``/docs/``, not ``/docs/Index``.

The one place case genuinely is not free is a page whose *name* is meant to be
cased — ``Indexing.md`` is not a landing page, and a file called ``INDEX.md``
is still the one file in that directory a generator would treat as its
homepage. So the fix is a case-insensitive comparison, not a relaxed one.
"""

from __future__ import annotations

import os

from pawprint.content import Page, collect, is_index_path, lead_page, parse_page, site_name
from pawprint.render import render_index


def _page(rel_path: str, text: str = "# A\n\nSome prose.\n") -> Page:
    return parse_page("/x/" + rel_path, rel_path, text)


def test_is_index_path_ignores_filename_case():
    assert is_index_path("Index.md")
    assert is_index_path("INDEX.md")
    assert is_index_path("index.MD")


def test_is_index_path_ignores_case_for_nested_landing_pages():
    assert is_index_path("docs/Index.md")
    assert is_index_path("docs/INDEX.MARKDOWN")


def test_is_index_path_ignores_case_for_both_content_suffixes():
    assert is_index_path("Index.markdown")
    assert is_index_path("Index.MARKDOWN")


def test_a_page_that_only_starts_with_index_is_not_a_landing_page():
    # The rule is about the whole filename, not a prefix of it. `Indexing.md`
    # and `index-old.md` are pages with those names.
    assert not is_index_path("Indexing.md")
    assert not is_index_path("index-old.md")
    assert not is_index_path("docs/Indexes.md")


def test_root_index_md_urls_to_the_origin():
    assert _page("Index.md").url == "/"


def test_nested_capitalised_index_urls_to_its_directory():
    assert _page("docs/Index.md").url == "/docs/"


def test_a_capitalised_index_is_not_the_site_name_from_a_sibling():
    # The regression the earlier `index.markdown` fix was about: the H1 of
    # llms.txt must come from the index, not from whatever page sorts first.
    pages = [
        _page("Index.md", "# Acme Docs\n\nThe real homepage.\n"),
        _page("changelog.md", "---\ndescription: What changed.\n---\nNotes.\n"),
    ]
    assert site_name(pages) == "Acme Docs"


def test_a_capitalised_index_is_the_lead_page():
    pages = [
        _page("aaa.md", "# Aaa\n\nFirst alphabetically.\n"),
        _page("Index.md", "# Acme Docs\n\nThe real homepage.\n"),
    ]
    assert lead_page(pages) is pages[1]


def test_generated_index_links_a_capitalised_index_to_the_origin(tmp_path):
    (tmp_path / "Index.md").write_text("# Acme Docs\n\nThe real homepage.\n")
    (tmp_path / "changelog.md").write_text(
        "---\ndescription: What changed.\n---\nNotes.\n"
    )
    rendered = render_index(collect(str(tmp_path)))
    assert "- [Acme Docs](/):" in rendered
    assert "/Index" not in rendered


def test_the_collect_walker_and_the_index_rule_agree_on_case(tmp_path):
    # The bug was a disagreement between two halves of the module: the walker
    # is case-insensitive about content suffixes, and the landing-page rule
    # was not. This asserts the walker still collects the capitalised file, so
    # the fix cannot be "stop collecting it" — the file is content, and it has
    # to be a landing page.
    (tmp_path / "Index.md").write_text("# Acme Docs\n\nThe real homepage.\n")
    pages = collect(str(tmp_path)).pages
    assert [p.rel_path for p in pages] == ["Index.md"]
    assert pages[0].url == "/"


def test_nested_capitalised_index_is_a_section_landing_page(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "Index.md").write_text("# Acme Docs\n\nThe real homepage.\n")
    (docs / "Index.md").write_text("# Guides\n\nGuides go here.\n")
    rendered = render_index(collect(str(tmp_path)))
    assert "- [Guides](/docs/):" in rendered
    assert "/docs/Index" not in rendered


def test_a_page_named_for_the_concept_of_an_index_is_left_alone():
    page = _page("Indexing.md", "# Indexing\n\nHow indexing works.\n")
    assert page.url == "/Indexing"
    assert not is_index_path("Indexing.md")
