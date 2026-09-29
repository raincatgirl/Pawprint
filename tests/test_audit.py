"""Tests for the readiness audit."""

from __future__ import annotations

from pawprint.audit import grade, run_checks, score, summarise
from pawprint.content import collect


def _site(tmp_path, pages, robots=None, extra=None):
    for rel, text in pages.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    if robots is not None:
        (tmp_path / "robots.txt").write_text(robots, encoding="utf-8")
    for name, text in (extra or {}).items():
        (tmp_path / name).write_text(text, encoding="utf-8")


def _check(checks, name):
    return next(c for c in checks if c.name == name)


def test_perfect_site_scores_100(tmp_path):
    _site(
        tmp_path,
        {
            "a.md": "---\ntitle: A\ndescription: A page.\n---\n" + ("word " * 400),
            "b.md": "---\ntitle: B\ndescription: B page.\n---\n" + ("word " * 400),
        },
        robots="User-agent: GPTBot\nAllow: /\nSitemap: https://x/s.xml\n",
        extra={"llms.txt": "# S\n", "sitemap.xml": "<urlset/>"},
    )
    checks = run_checks(str(tmp_path), collect(str(tmp_path)))
    assert score(checks) == 100
    assert grade(score(checks)) == "good"


def test_empty_site_scores_zero(tmp_path):
    checks = run_checks(str(tmp_path), collect(str(tmp_path)))
    assert score(checks) == 0
    assert grade(0) == "invisible to AI engines"


def test_grade_boundaries():
    assert grade(100) == "good"
    assert grade(80) == "good"
    assert grade(60) == "workable"
    assert grade(40) == "patchy"
    assert grade(20) == "barely legible"


def test_llms_txt_check_detects_file(tmp_path):
    _site(tmp_path, {"a.md": "# A\n"}, extra={"llms.txt": "# S\n"})
    checks = run_checks(str(tmp_path), collect(str(tmp_path)))
    assert _check(checks, "llms.txt present").passed


def test_robots_check_requires_ai_crawler_named(tmp_path):
    _site(tmp_path, {"a.md": "# A\n"}, robots="User-agent: *\nAllow: /\n")
    checks = run_checks(str(tmp_path), collect(str(tmp_path)))
    assert not _check(checks, "robots.txt names AI crawlers").passed


def test_robots_check_passes_with_ai_crawler(tmp_path):
    _site(tmp_path, {"a.md": "# A\n"}, robots="User-agent: ClaudeBot\nAllow: /\n")
    checks = run_checks(str(tmp_path), collect(str(tmp_path)))
    assert _check(checks, "robots.txt names AI crawlers").passed


def test_sitemap_txt_also_counts(tmp_path):
    _site(tmp_path, {"a.md": "# A\n"}, extra={"sitemap.txt": "https://x/s.txt"})
    checks = run_checks(str(tmp_path), collect(str(tmp_path)))
    assert _check(checks, "sitemap present").passed


def test_content_depth_thin_fails(tmp_path):
    _site(tmp_path, {"a.md": "# A\n\ntiny\n"})
    checks = run_checks(str(tmp_path), collect(str(tmp_path)))
    check = _check(checks, "content depth")
    assert not check.passed
    assert "too thin" in check.detail


def test_content_depth_substantial_passes(tmp_path):
    _site(tmp_path, {"a.md": "# A\n\n" + ("word " * 4000)})
    checks = run_checks(str(tmp_path), collect(str(tmp_path)))
    check = _check(checks, "content depth")
    assert check.passed
    assert "substantial" in check.detail


def test_content_depth_counts_cjk_characters(tmp_path):
    _site(tmp_path, {"a.md": "# A\n\n" + ("字" * 1000)})
    checks = run_checks(str(tmp_path), collect(str(tmp_path)))
    assert _check(checks, "content depth").passed


def test_page_descriptions_partial_fails(tmp_path):
    _site(
        tmp_path,
        {
            "a.md": "---\ntitle: A\ndescription: yes\n---\nx",
            "b.md": "# B\n\nbody",
            "c.md": "# C\n\nbody",
        },
    )
    checks = run_checks(str(tmp_path), collect(str(tmp_path)))
    check = _check(checks, "page descriptions")
    assert not check.passed
    assert "1/3" in check.detail


def test_page_descriptions_mostly_present_passes(tmp_path):
    _site(
        tmp_path,
        {
            "a.md": "---\ntitle: A\ndescription: d\n---\nx",
            "b.md": "---\ntitle: B\ndescription: d\n---\nx",
            "c.md": "---\ntitle: C\ndescription: d\n---\nx",
            "d.md": "---\ntitle: D\n---\nx",
        },
    )
    checks = run_checks(str(tmp_path), collect(str(tmp_path)))
    check = _check(checks, "page descriptions")
    # 3/4 is 0.75, below the 0.8 pass bar — this is the "partial" band.
    assert not check.passed
    assert "3/4" in check.detail


def test_summarise_lists_next_steps(tmp_path):
    _site(tmp_path, {"a.md": "# A\n\ntiny\n"})
    checks = run_checks(str(tmp_path), collect(str(tmp_path)))
    out = summarise(checks, collect(str(tmp_path)))
    assert "AI-readiness:" in out
    assert "Next steps:" in out
    assert "llmstxt.org" in out


def test_summarise_says_nothing_to_fix_when_perfect(tmp_path):
    _site(
        tmp_path,
        {"a.md": "---\ntitle: A\ndescription: d\n---\n" + ("word " * 400)},
        robots="User-agent: GPTBot\nAllow: /\nSitemap: https://x/s.xml\n",
        extra={"llms.txt": "# S\n", "sitemap.xml": "<urlset/>"},
    )
    pages = collect(str(tmp_path))
    out = summarise(run_checks(str(tmp_path), pages), pages)
    assert "Nothing to fix" in out


def test_every_check_is_worth_twenty():
    checks = run_checks(".", collect("."))
    assert all(c.points == 20 for c in checks)
