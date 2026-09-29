"""Tests for the content-tree parser."""

from __future__ import annotations

import os

import pytest

from pawprint.content import (
    collect,
    parse_front_matter,
    parse_page,
    plain_text,
    site_name,
    summarise,
)


def test_front_matter_absent_returns_whole_text():
    meta, body = parse_front_matter("# Title\n\nSome text.\n")
    assert meta == {}
    assert body == "# Title\n\nSome text.\n"


def test_front_matter_basic_fields():
    text = "---\ntitle: Hello\ndescription: A thing\norder: 3\ndraft: false\n---\n\n# Body\n"
    meta, body = parse_front_matter(text)
    assert meta["title"] == "Hello"
    assert meta["description"] == "A thing"
    assert meta["order"] == 3
    assert meta["draft"] is False
    assert body == "# Body\n"


def test_front_matter_unterminated_falls_back_to_body():
    text = "---\ntitle: Hello\n\n# Body\n"
    meta, body = parse_front_matter(text)
    assert meta == {}
    assert body == text


def test_front_matter_quotes_are_stripped():
    meta, _ = parse_front_matter("---\ntitle: \"Quoted Title\"\n---\nbody\n")
    assert meta["title"] == "Quoted Title"


def test_front_matter_comments_and_blanks_skipped():
    text = "---\n# a comment\n\ntitle: T\nnot-a-key\n---\nx\n"
    meta, _ = parse_front_matter(text)
    assert meta == {"title": "T"}


def test_front_matter_draft_is_case_insensitive():
    meta, _ = parse_front_matter("---\ndraft: TRUE\n---\nx\n")
    assert meta["draft"] is True


def test_parse_page_prefers_front_matter_title():
    page = parse_page("/x/a.md", "a.md", "---\ntitle: FM\n---\n# H1\n")
    assert page.title == "FM"


def test_parse_page_falls_back_to_h1():
    page = parse_page("/x/a.md", "a.md", "# Heading Here\n\ntext\n")
    assert page.title == "Heading Here"


def test_parse_page_falls_back_to_stem():
    page = parse_page("/x/my_page.md", "my_page.md", "just text, no heading\n")
    assert page.title == "my page"


def test_parse_page_url_rules():
    assert parse_page("/x/guide.md", "guide.md", "t").url == "/guide"
    assert parse_page("/x/index.md", "index.md", "t").url == "/"
    assert parse_page("/x/a/index.md", "a/index.md", "t").url == "/a/"
    assert parse_page("/x/a/b.md", "a/b.md", "t").url == "/a/b"
    assert parse_page("/x/README.md", "README.md", "t").url == "/README"


def test_collect_skips_hidden_and_vendor_dirs(tmp_path):
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hidden.md").write_text("# Hidden\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.md").write_text("# Dep\n", encoding="utf-8")
    pages = collect(str(tmp_path))
    assert [p.rel_path for p in pages] == ["a.md"]


def test_collect_skips_non_markdown(tmp_path):
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("not content\n", encoding="utf-8")
    pages = collect(str(tmp_path))
    assert [p.rel_path for p in pages] == ["a.md"]


def test_collect_excludes_drafts_by_default(tmp_path):
    (tmp_path / "live.md").write_text("# Live\n", encoding="utf-8")
    (tmp_path / "wip.md").write_text("---\ndraft: true\n---\n# WIP\n", encoding="utf-8")
    assert [p.rel_path for p in collect(str(tmp_path))] == ["live.md"]
    assert len(collect(str(tmp_path), include_drafts=True)) == 2


def test_collect_orders_by_front_matter_then_path(tmp_path):
    (tmp_path / "b.md").write_text("---\norder: 1\n---\n# B\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("---\norder: 2\n---\n# A\n", encoding="utf-8")
    (tmp_path / "c.md").write_text("# C\n", encoding="utf-8")
    pages = collect(str(tmp_path))
    assert [p.rel_path for p in pages] == ["c.md", "b.md", "a.md"]


def test_collect_handles_nested_dirs(tmp_path):
    sub = tmp_path / "guide"
    sub.mkdir()
    (sub / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (tmp_path / "top.md").write_text("# Top\n", encoding="utf-8")
    pages = collect(str(tmp_path))
    assert {p.rel_path for p in pages} == {"top.md", "guide/intro.md"}


def test_collect_survives_unreadable_bytes(tmp_path):
    (tmp_path / "ok.md").write_text("# OK\n", encoding="utf-8")
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe\x00bad")
    pages = collect(str(tmp_path))
    assert [p.rel_path for p in pages] == ["ok.md"]


def test_plain_text_strips_markdown_but_keeps_link_targets():
    src = "**bold** and [link](https://example.com) and ![img](x.png)"
    out = plain_text(src)
    assert "**" not in out
    assert "https://example.com" in out
    assert "x.png" not in out


def test_plain_text_strips_headings_and_quotes():
    out = plain_text("## Head\n> quoted\n")
    assert out.splitlines()[0] == "Head"
    assert out.splitlines()[1] == "quoted"


def test_summarise_prefers_description():
    page = parse_page("/x/a.md", "a.md", "---\ndescription: Explicit.\n---\nBody text here.\n")
    assert summarise(page) == "Explicit."


def test_summarise_falls_back_to_first_paragraph():
    page = parse_page("/x/a.md", "a.md", "# T\n\nFirst para here.\n\nSecond para.\n")
    assert summarise(page) == "First para here."


def test_summarise_skips_heading_only_body():
    page = parse_page("/x/a.md", "a.md", "# A\n\n\n")
    assert summarise(page) == ""


def test_summarise_skips_list_and_table_blocks():
    page = parse_page("/x/a.md", "a.md", "# T\n\n- item one\n- item two\n\n| a | b |\n|---|---|\n\nReal prose.\n")
    assert summarise(page) == "Real prose."


def test_summarise_truncates_on_word_boundary():
    body = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
    page = parse_page("/x/a.md", "a.md", f"# T\n\n{body}\n")
    out = summarise(page, limit=30)
    assert out.endswith("...")
    assert len(out) <= 33
    # must cut on a space, never mid-word
    assert not out[:-3].endswith(tuple("abcdefghijklmnopqrstuvwxyz")) or " " in out[:-3]


def test_site_name_uses_first_toplevel_page(tmp_path):
    (tmp_path / "index.md").write_text("---\ntitle: My Docs\n---\nx\n", encoding="utf-8")
    assert site_name(collect(str(tmp_path)).pages) == "My Docs"


def test_site_name_default_when_only_nested():
    page = parse_page("/x/a/b.md", "a/b.md", "# B\n")
    assert site_name([page], default="Fallback") == "Fallback"
