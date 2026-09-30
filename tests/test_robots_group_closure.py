"""A blank line ends a group even when that group stated no rules.

RFC 9309's grammar is ``group = startgroupline *(startgroupline)
*(ruleline / emptyline)``. A group is one or more ``User-agent`` lines
followed by rules *and/or* blank lines, so a blank line after a group closes
it even when no rule was ever stated. The next ``User-agent`` line then opens
a fresh group.

Pawprint only closed a group at a blank line once a rule had been seen
(``if sealed:``). So this file:

    User-agent: *

    User-agent: GPTBot
    Disallow: /

parsed the two lines as one group with two members, and GPTBot's ``Disallow: /``
leaked backwards into the wildcard. Every crawler fell through to that
wildcard and read as ``blocked`` — a false claim about who can read the site,
in the direction that hides an open door, on a file whose only intent was to
block one crawler.
"""

from __future__ import annotations

from pawprint.crawlers import CRAWLERS, audit_policy, parse_robots, recommendations, verdict


def crawler(name: str):
    return next(c for c in CRAWLERS if c.name == name)


TEXT = "User-agent: *\n\nUser-agent: GPTBot\nDisallow: /\n"


def test_gptbot_rule_does_not_leak_back_into_the_wildcard():
    assert parse_robots(TEXT)["groups"].get("*") == []


def test_a_crawler_the_file_never_blocks_is_allowed():
    # Nothing in this file disallows ClaudeBot. The file says "block GPTBot",
    # and the wildcard group above it states no rule at all.
    assert verdict(crawler("ClaudeBot"), parse_robots(TEXT)) == "allowed"


def test_the_named_crawler_is_still_blocked():
    # The other half: closing the wildcard at the blank line must not lose
    # the group that does state rules.
    assert verdict(crawler("GPTBot"), parse_robots(TEXT)) == "blocked"


def test_every_other_crawler_is_allowed():
    robots = parse_robots(TEXT)
    for c in CRAWLERS:
        if c.name == "GPTBot":
            continue
        assert verdict(c, robots) == "allowed", c.name


def test_a_wildcard_placeholder_followed_by_a_rule_does_not_close_the_site():
    # The shape people actually write while still deciding: start a
    # placeholder wildcard, then get round to the crawler you meant to block.
    rows = dict((n, v) for n, v, _ in audit_policy(TEXT))
    assert rows["GPTBot"] == "blocked"
    assert rows["ClaudeBot"] == "allowed"


def test_recommendations_do_not_blame_the_wildcard():
    recs = "\n".join(recommendations(TEXT + "Sitemap: https://x/s.xml\n"))
    # Only GPTBot is blocked, so there is no "these cannot read you" line to
    # give. Blaming the wildcard would point the author at a `Disallow` that
    # is not in the file, which is the false-claim failure mode this file
    # tripped.
    assert "cannot read you" not in recs
    assert "wildcard" not in recs
    # GPTBot is still named as not reading the site, which is true.
    assert "GPTBot" in recs


def test_a_blank_line_between_user_agents_of_one_group_still_shares_rules():
    # The multi-agent group form must keep working. A blank line between two
    # User-agent lines with no rules yet closes the first as an empty group,
    # which imposes nothing — so the rules below still land on both names,
    # because an empty group is a group that says nothing and the named
    # group carries the rule.
    out = parse_robots("User-agent: A\n\nUser-agent: B\nDisallow: /x\n")
    assert out["groups"]["a"] == []
    assert out["groups"]["b"] == [(False, "/x")]


def test_consecutive_user_agents_with_no_blank_line_still_share_rules():
    out = parse_robots("User-agent: A\nUser-agent: B\nDisallow: /x\n")
    assert out["groups"]["a"] == [(False, "/x")]
    assert out["groups"]["b"] == [(False, "/x")]


def test_blank_line_still_separates_two_groups_that_both_state_rules():
    # The pre-existing behaviour this change must not disturb.
    out = parse_robots("User-agent: A\nDisallow: /x\n\nUser-agent: B\nDisallow: /y\n")
    assert out["groups"]["a"] == [(False, "/x")]
    assert out["groups"]["b"] == [(False, "/y")]
