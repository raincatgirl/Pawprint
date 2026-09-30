"""A byte-order mark is an encoding artefact, not content.

Every file in a site can be written with a UTF-8 BOM — it is what a lot of
editors on Windows produce, and what a generator that does not strip it
passes straight through. Reading the file with ``encoding="utf-8"`` keeps the
BOM as the character U+FEFF, and it becomes the first character of the text.

That character is at the exact position the front-matter fence has to occupy.
``parse_front_matter`` tests ``text.startswith("---")``, so a BOM in front of
it is false, the metadata block is never recognised, and the *whole file*
falls through to the tolerant branch: the whole text is the body and the
mapping is empty.

The consequences are not cosmetic, and they are all on the paths this tool
exists to get right:

- the front matter is no longer metadata, so it is part of the page body and
  is written verbatim into ``llms-full.txt``, raw YAML and all;
- with no ``title:`` in metadata, the title falls back to the first heading,
  and there is none in a page whose only heading was front matter's own
  ``---`` lines, so it falls back again to the filename;
- the H1 of ``llms.txt`` — the one line that names the site to an AI engine —
  came out as ``﻿--- title: Acme Docs description: ...``, the site's own
  front matter flattened into a single line;
- with no ``description:`` in metadata, audit check 5 reported ``0/2 pages
  have one`` for a site where every page had one, and the report told the
  author to add descriptions they had already written.

So one invisible byte at the top of a file silently removed the title, the
description, and the clean text of every page it appeared in.

The mark is stripped at the point where the fence is looked for, not in the
caller, because ``parse_page`` is public: a caller that reads a file itself
must get the same answer as :func:`~pawprint.content.collect`, which reads
from disk.
"""

from __future__ import annotations

import os

from pawprint.content import collect, parse_front_matter, parse_page
from pawprint.render import render_full, render_index

BOM = "﻿"

FM = (
    BOM + "---\n"
    "title: Acme Docs\n"
    "description: The real description of the site.\n"
    "---\n\n"
    "Acme is a widget service for teams.\n"
)


def test_front_matter_is_read_from_a_file_that_opens_with_a_bom():
    meta, body = parse_front_matter(FM)
    assert meta["title"] == "Acme Docs"
    assert meta["description"] == "The real description of the site."
    assert "title:" not in body


def test_a_bom_does_not_survive_into_the_body():
    meta, body = parse_front_matter(FM)
    assert not body.startswith(BOM)
    assert BOM not in body


def test_a_bom_does_not_appear_in_a_page_title():
    page = parse_page("/x/index.md", "index.md", FM)
    assert page.title == "Acme Docs"
    assert page.description == "The real description of the site."


def test_a_page_with_a_bom_takes_the_same_path_as_one_without():
    with_bom = parse_page("/x/index.md", "index.md", FM)
    without = parse_page("/x/index.md", "index.md", FM[len(BOM) :])
    assert with_bom.title == without.title
    assert with_bom.description == without.description
    assert with_bom.body == without.body


def test_a_bom_on_a_file_with_no_front_matter_is_still_stripped():
    # The mark is not part of the document's text, so a page that never had
    # front matter must not grow a leading U+FEFF in its body either — that
    # would reach the word count and the first-heading reader as content.
    meta, body = parse_front_matter(BOM + "# Title\n\nSome prose.\n")
    assert meta == {}
    assert body.startswith("# Title")
    assert BOM not in body


def test_a_bom_makes_no_difference_to_the_generated_index(tmp_path):
    (tmp_path / "index.md").write_text(FM, encoding="utf-8")
    (tmp_path / "guide.md").write_text(
        "---\ntitle: Guide\ndescription: How to use the widget.\n---\n\n"
        "The guide explains the widget end to end.\n",
        encoding="utf-8",
    )
    marked = render_index(collect(str(tmp_path)))

    for name in ("index.md", "guide.md"):
        path = tmp_path / name
        path.write_text(path.read_text(encoding="utf-8").lstrip(BOM), encoding="utf-8")
    plain = render_index(collect(str(tmp_path)))

    assert marked == plain
    assert marked.splitlines()[0] == "# Acme Docs"
    assert BOM not in marked


def test_a_bom_on_disk_does_not_leak_front_matter_into_the_full_text(tmp_path):
    (tmp_path / "index.md").write_text(FM, encoding="utf-8")
    full = render_full(collect(str(tmp_path)))
    assert "title: Acme Docs" not in full
    assert BOM not in full
    assert full.splitlines()[0] == "# Acme Docs"


def test_a_bom_on_disk_does_not_cost_the_page_its_description(tmp_path):
    (tmp_path / "index.md").write_text(FM, encoding="utf-8")
    pages = collect(str(tmp_path))
    assert [p.description for p in pages] == [
        "The real description of the site."
    ]


def test_a_bom_is_only_stripped_from_the_front_of_the_file(tmp_path):
    # A U+FEFF in the middle of a document is a zero-width no-break space,
    # which some real pages use deliberately. Only the encoding mark at the
    # very start is an artefact.
    text = "---\ntitle: T\n---\n\nCafé" + BOM + " time.\n"
    meta, body = parse_front_matter(text)
    assert meta["title"] == "T"
    assert BOM in body


def test_a_second_bom_is_not_stripped_and_keeps_the_fence_from_being_front_matter():
    # Only the encoding mark is removed, once. A second one is a
    # zero-width no-break space, which is content — so it sits in front of
    # the opening fence and the block is not front matter after all. The
    # tolerant branch is the right answer here: read the file as prose and
    # do not guess that the first `---` was meant as a fence.
    meta, body = parse_front_matter(BOM + BOM + "---\ntitle: T\n---\n\nProse.\n")
    assert meta == {}
    assert body.startswith(BOM)
    assert BOM in body


def test_a_bom_followed_by_no_front_matter_still_yields_a_heading(tmp_path):
    (tmp_path / "index.md").write_text(
        BOM + "# Real Heading\n\nProse about the thing.\n", encoding="utf-8"
    )
    pages = collect(str(tmp_path))
    assert [p.title for p in pages] == ["Real Heading"]


def test_a_file_that_is_only_a_bom_is_empty_content_not_a_crash(tmp_path):
    (tmp_path / "index.md").write_text(BOM, encoding="utf-8")
    assert os.path.exists(str(tmp_path / "index.md"))
    pages = collect(str(tmp_path))
    assert len(pages) == 1
    assert pages.pages[0].title == "index"
