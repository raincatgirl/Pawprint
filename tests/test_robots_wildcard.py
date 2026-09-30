"""Wildcard groups and empty Disallow rules, which Pawprint used to ignore.

A robots.txt that says only ``User-agent: *`` applies to every crawler that
is not named explicitly. Pawprint looked up each AI crawler by name, found
nothing, and reported "unlisted" — so a site that had just written
``User-agent: * / Disallow: /`` was told that GPTBot was merely unlisted
rather than blocked, and that it should go add explicit groups. The advice
was confident and wrong, in the direction that hides a block.

Separately, RFC 9309 reads ``Disallow:`` with an empty value as "no path is
disallowed", i.e. an allow-everything. The parser stored it as the block
``(False, "")``, and ``verdict`` treats ``""`` as a block of the whole site.
"""

from __future__ import annotations

from pawprint.crawlers import CRAWLERS, audit_policy, parse_robots, recommendations, verdict


def crawler(name: str):
    return next(c for c in CRAWLERS if c.name == name)


def test_wildcard_disallow_everything_blocks_every_named_crawler():
    # The canonical "no AI crawlers" file. Every crawler is blocked.
    robots = parse_robots("User-agent: *\nDisallow: /\n")
    for c in CRAWLERS:
        assert verdict(c, robots) == "blocked", c.name


def test_wildcard_allow_everything_allows_every_named_crawler():
    # The most common robots.txt on the web.
    robots = parse_robots("User-agent: *\nAllow: /\n")
    for c in CRAWLERS:
        assert verdict(c, robots) == "allowed", c.name


def test_explicit_group_overrides_the_wildcard():
    # A site that blocks all crawlers but opts GPTBot back in.
    robots = parse_robots(
        "User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\nAllow: /\n"
    )
    assert verdict(crawler("GPTBot"), robots) == "allowed"
    assert verdict(crawler("ClaudeBot"), robots) == "blocked"


def test_narrow_wildcard_block_reads_as_partial():
    robots = parse_robots("User-agent: *\nAllow: /\nDisallow: /admin\n")
    assert verdict(crawler("GPTBot"), robots) == "partial"


def test_empty_disallow_is_an_allow_not_a_block():
    # RFC 9309: "Disallow:" with an empty value disallows nothing.
    robots = parse_robots("User-agent: *\nDisallow:\n")
    assert verdict(crawler("GPTBot"), robots) == "allowed"


def test_empty_disallow_on_a_named_group_is_an_allow():
    robots = parse_robots("User-agent: GPTBot\nDisallow:\n")
    assert verdict(crawler("GPTBot"), robots) == "allowed"


def test_unlisted_means_no_group_and_no_wildcard():
    # Only a sitemap, or nothing an AI crawler can match.
    robots = parse_robots("Sitemap: https://x/s.xml\n")
    assert verdict(crawler("GPTBot"), robots) == "unlisted"
    assert verdict(crawler("GPTBot"), parse_robots("")) == "unlisted"


def test_wildcard_block_is_reported_as_blocked_not_as_an_add_group_suggestion():
    rows = dict((n, v) for n, v, _ in audit_policy("User-agent: *\nDisallow: /\n"))
    assert rows["GPTBot"] == "blocked"

    recs = recommendations("User-agent: *\nDisallow: /\nSitemap: https://x/s.xml\n")
    # It should say the site is closed to citation crawlers, not tell the
    # reader that the fix is to go and add groups for each one.
    assert not any("Not reading you" in r for r in recs)
    assert any("Disallow" in r for r in recs)


def test_wildcard_allow_needs_no_crawler_advice():
    recs = recommendations("User-agent: *\nAllow: /\nSitemap: https://x/s.xml\n")
    # Nobody is blocked, so there is no "go add a group" advice. The
    # training-crawler warning still fires, and should: a blanket `Allow: /`
    # does hand CCBot and friends the whole site.
    assert not any("Not reading you" in r for r in recs)
    assert any("Training crawlers" in r for r in recs)


def test_unreachable_ignores_the_wildcard():
    # The wildcard is not a named crawler, so it must not appear as one, and
    # must not stop the real gaps from being listed.
    out = parse_robots("User-agent: *\nAllow: /\n")
    assert "*" not in out["unreachable"]
    assert "GPTBot" in out["unreachable"]
