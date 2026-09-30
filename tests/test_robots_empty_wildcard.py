"""A wildcard group with no rules in it, which Pawprint used to call closed.

A group imposes rules only where it states them. ``User-agent: *`` followed
by nothing is the same empty group last tick fixed for a *named* crawler, and
RFC 9309 reads it the same way: no rules, so nothing is disallowed and the
site is open.

Pawprint only tested for an empty group on the named-agent branch. A crawler
that fell through to the wildcard got an empty rule list, saw no blocks and no
allows, and was reported "unlisted" -- which then read downstream as "this
site has said nothing about GPTBot". Worse, ``recommendations`` turned that
into a confident false claim::

    A wildcard `User-agent: *` group is closed to citation crawlers, so these
    cannot read you: GPTBot, ...

There is no ``Disallow`` in the file. The advice told the author to relax a
restriction they never wrote.
"""

from __future__ import annotations

from pawprint.crawlers import CRAWLERS, audit_policy, parse_robots, recommendations, verdict


def crawler(name: str):
    return next(c for c in CRAWLERS if c.name == name)


def test_empty_wildcard_group_allows_every_crawler():
    robots = parse_robots("User-agent: *\n")
    for c in CRAWLERS:
        assert verdict(c, robots) == "allowed", c.name


def test_empty_wildcard_group_is_not_reported_as_closed():
    rows = dict((n, v) for n, v, _ in audit_policy("User-agent: *\n"))
    assert rows["GPTBot"] == "allowed"
    assert rows["CCBot"] == "allowed"


def test_recommendations_do_not_call_an_empty_wildcard_closed():
    advice = "\n".join(recommendations("User-agent: *\n"))
    assert "cannot read you" not in advice
    assert "Relax the wildcard" not in advice


def test_recommendations_do_not_tell_the_author_to_add_groups_they_do_not_need():
    # Every crawler matches the wildcard, so no group is missing and there is
    # nothing to add. Only the training-crawler warning and the sitemap note
    # should remain.
    advice = "\n".join(recommendations("User-agent: *\n"))
    assert "Not reading you" not in advice
    assert "Add an explicit `User-agent:` group" not in advice


def test_training_crawlers_are_still_flagged_under_an_empty_wildcard():
    # The one true thing the tool can say about an empty wildcard: nothing is
    # blocked, which also means nothing is protected.
    advice = "\n".join(recommendations("User-agent: *\n"))
    assert "Training crawlers currently allowed" in advice


def test_a_named_block_is_not_weakened_by_the_empty_group_fix():
    # The fix moves the empty-group check after group selection, so it now
    # also runs on the named branch. A group that *does* state rules must
    # still be read.
    robots = parse_robots("User-agent: GPTBot\nDisallow: /\n")
    assert verdict(crawler("GPTBot"), robots) == "blocked"
    assert verdict(crawler("ClaudeBot"), robots) == "unlisted"


def test_a_wildcard_with_only_a_sitemap_line_is_still_unlisted():
    # Naming the wildcard while stating no rules for it is a group. A file
    # that only has a Sitemap names no group at all, and that is different.
    robots = parse_robots("Sitemap: https://x/s.xml\n")
    assert verdict(crawler("GPTBot"), robots) == "unlisted"


def test_comment_only_wildcard_group_is_still_a_group():
    # The comment is stripped, leaving the same empty group.
    robots = parse_robots("# block the bots\nUser-agent: *\n# nothing follows\n")
    assert verdict(crawler("GPTBot"), robots) == "allowed"
