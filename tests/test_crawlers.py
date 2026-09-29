"""Tests for robots.txt parsing and crawler verdicts."""

from __future__ import annotations

from pawprint.crawlers import (
    CRAWLERS,
    ROBOTS_SAMPLE,
    audit_policy,
    parse_robots,
    recommendations,
    verdict,
)


def test_parse_empty_robots():
    out = parse_robots("")
    assert out["groups"] == {}
    assert out["sitemaps"] == []


def test_parse_wildcard_group():
    out = parse_robots("User-agent: *\nAllow: /\n")
    assert ("*" in out["groups"]) is True


def test_parse_sitemap_line():
    out = parse_robots("Sitemap: https://example.com/sitemap.xml\n")
    assert out["sitemaps"] == ["https://example.com/sitemap.xml"]


def test_parse_comments_are_ignored():
    out = parse_robots("# comment\nUser-agent: GPTBot\nAllow: /\n")
    assert "gptbot" in out["groups"]


def test_multiple_user_agents_share_rules():
    out = parse_robots("User-agent: A\nUser-agent: B\nDisallow: /private\n")
    assert ("gptbot" in out["groups"]) is False
    assert len(out["groups"]["a"]) == 1
    assert len(out["groups"]["b"]) == 1


def test_unreachable_lists_named_crawlers():
    out = parse_robots("User-agent: GPTBot\nAllow: /\n")
    assert "ClaudeBot" in out["unreachable"]
    assert "GPTBot" not in out["unreachable"]


def test_verdict_allowed():
    c = next(x for x in CRAWLERS if x.name == "GPTBot")
    robots = parse_robots("User-agent: GPTBot\nAllow: /\n")
    assert verdict(c, robots) == "allowed"


def test_verdict_blocked():
    c = next(x for x in CRAWLERS if x.name == "GPTBot")
    robots = parse_robots("User-agent: GPTBot\nDisallow: /\n")
    assert verdict(c, robots) == "blocked"


def test_verdict_unlisted():
    c = next(x for x in CRAWLERS if x.name == "GPTBot")
    assert verdict(c, parse_robots("User-agent: *\nAllow: /\n")) == "unlisted"


def test_verdict_partial_for_narrow_blocks():
    c = next(x for x in CRAWLERS if x.name == "GPTBot")
    robots = parse_robots("User-agent: GPTBot\nAllow: /\nDisallow: /admin\n")
    assert verdict(c, robots) == "partial"


def test_audit_policy_covers_every_crawler():
    rows = audit_policy("User-agent: *\nAllow: /\n")
    assert len(rows) == len(CRAWLERS)
    assert {n for n, _, _ in rows} == {c.name for c in CRAWLERS}


def test_audit_policy_flags_blocked_citation_crawler():
    rows = dict((n, (v, note)) for n, v, note in audit_policy("User-agent: GPTBot\nDisallow: /\n"))
    assert rows["GPTBot"][0] == "blocked"
    assert "want this one" in rows["GPTBot"][1]


def test_recommendations_flag_missing_sitemap():
    recs = recommendations("User-agent: *\nAllow: /\n")
    assert any("Sitemap" in r for r in recs)


def test_recommendations_praise_present_sitemap():
    recs = recommendations("Sitemap: https://x/s.xml\nUser-agent: *\nAllow: /\n")
    assert any("good" in r for r in recs)


def test_recommendations_list_blocked_wanted_crawlers():
    recs = recommendations("User-agent: GPTBot\nDisallow: /\nSitemap: https://x/s.xml\n")
    assert any("GPTBot" in r for r in recs)


def test_recommendations_flag_open_training_crawlers():
    recs = recommendations("User-agent: CCBot\nAllow: /\nSitemap: https://x/s.xml\n")
    assert any("Training crawlers" in r for r in recs)


def test_sample_robots_is_parseable_and_allows_everything():
    robots = parse_robots(ROBOTS_SAMPLE)
    for c in CRAWLERS:
        assert verdict(c, robots) in ("allowed", "unlisted")
    assert robots["sitemaps"]
