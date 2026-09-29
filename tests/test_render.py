"""Tests for llms.txt / llms-full.txt rendering."""

from __future__ import annotations

from pawprint.content import collect, parse_page
from pawprint.render import render_full, render_index


def _page(tmp_path, rel, text):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_index_has_h1_blockquote_and_sections(tmp_path):
    _page(tmp_path, "index.md", "---\ntitle: Docs\ndescription: The docs.\n---\n# Docs\n")
    _page(tmp_path, "guide/intro.md", "---\ntitle: Intro\ndescription: Start here.\n---\nbody\n")
    pages = collect(str(tmp_path))
    out = render_index(pages)

    assert out.startswith("# Docs\n")
    assert "> The docs." in out
    assert "## Pages" in out
    assert "## Guide" in out
    assert "- [Intro](/guide/intro): Start here." in out


def test_index_groups_top_level_segments(tmp_path):
    _page(tmp_path, "alpha/a.md", "# A\n")
    _page(tmp_path, "beta/b.md", "# B\n")
    out = render_index(collect(str(tmp_path)))
    assert "## Alpha" in out
    assert "## Beta" in out


def test_index_handles_empty_tree(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    out = render_index(collect(str(tmp_path)))
    assert "_(no content pages found)_" in out


def test_index_links_become_absolute_with_base_url(tmp_path):
    _page(tmp_path, "guide/intro.md", "---\ntitle: Intro\n---\nbody\n")
    out = render_index(collect(str(tmp_path)), base_url="https://example.com")
    assert "(https://example.com/guide/intro)" in out


def test_index_base_url_trailing_slash_is_normalised(tmp_path):
    _page(tmp_path, "a.md", "# A\n")
    out = render_index(collect(str(tmp_path)), base_url="https://example.com/")
    assert "https://example.com/a.md" not in out
    assert "https://example.com/a" in out


def test_index_always_offers_full_text_and_spec(tmp_path):
    _page(tmp_path, "a.md", "# A\n")
    out = render_index(collect(str(tmp_path)))
    assert "llms-full.txt" in out
    assert "llmstxt.org" in out


def test_index_entry_without_summary_has_no_colon(tmp_path):
    _page(tmp_path, "a.md", "# A\n\n\n")
    out = render_index(collect(str(tmp_path)))
    line = next(l for l in out.splitlines() if l.startswith("- [A]"))
    assert line.endswith(")")


def test_index_name_override(tmp_path):
    _page(tmp_path, "a.md", "---\ntitle: Page Title\n---\nx\n")
    out = render_index(collect(str(tmp_path)), name="Override")
    assert out.startswith("# Override")


def test_full_contains_every_page_with_source(tmp_path):
    _page(tmp_path, "a.md", "# Alpha\n\nalpha body\n")
    _page(tmp_path, "b.md", "# Beta\n\nbeta body\n")
    out = render_full(collect(str(tmp_path)))
    assert "# Alpha" in out and "alpha body" in out
    assert "# Beta" in out and "beta body" in out
    assert "Source: /a" in out and "Source: /b" in out
    assert "---" in out


def test_full_empty_tree(tmp_path):
    out = render_full(collect(str(tmp_path)))
    assert "_(no content pages found)_" in out
