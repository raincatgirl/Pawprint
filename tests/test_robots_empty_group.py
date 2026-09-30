"""A named group with no rules in it, which Pawprint used to call unlisted.

RFC 9309 says a crawler matches the *most specific* group that names it. A
group that is named but carries no rules imposes none, so the crawler is
unrestricted. This is the ordinary way to opt a single crawler in::

    User-agent: *
    Disallow: /

    User-agent: GPTBot

The author has plainly opened the door for GPTBot, and the wildcard's
``Disallow`` does not apply to it any more. Pawprint read the group as empty,
reported GPTBot as "unlisted", and then told the author their wildcard was
closed to it — advice to edit a line that was not what was stopping the
crawler, and a false statement about who can read the site.
"""

from __future__ import annotations

from pawprint.crawlers import CRAWLERS, audit_policy, parse_robots, recommendations, verdict


def crawler(name: str):
    return next(c for c in CRAWLERS if c.name == name)


def test_empty_named_group_is_unrestricted_despite_a_blocking_wildcard():
    robots = parse_robots("User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\n")
    assert verdict(crawler("GPTBot"), robots) == "allowed"


def test_empty_named_group_does_not_open_the_wildcard_to_its_siblings():
    # Only GPTBot gets the door open. Everyone else still meets `Disallow: /`.
    robots = parse_robots("User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\n")
    assert verdict(crawler("ClaudeBot"), robots) == "blocked"


def test_a_group_naming_several_agents_opens_the_door_for_all_of_them():
    robots = parse_robots(
        "User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\nUser-agent: ClaudeBot\n"
    )
    assert verdict(crawler("GPTBot"), robots) == "allowed"
    assert verdict(crawler("ClaudeBot"), robots) == "allowed"
    assert verdict(crawler("PerplexityBot"), robots) == "blocked"


def test_recommendations_do_not_advise_editing_the_wildcard_for_a_crawler_that_has_a_group():
    text = "User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\n"
    advice = "\n".join(recommendations(text))
    assert "GPTBot" not in advice
    # ...but a crawler with no group at all is still a real gap, and is named.
    assert "ClaudeBot" in advice


def test_empty_named_group_beats_an_empty_wildcard_group():
    # `Disallow:` with no value allows everything, so the wildcard already
    # allows everyone. Naming a crawler must not make it worse.
    robots = parse_robots("User-agent: *\nDisallow:\n\nUser-agent: GPTBot\n")
    assert verdict(crawler("GPTBot"), robots) == "allowed"
    assert verdict(crawler("ClaudeBot"), robots) == "allowed"


def test_recommendations_blame_the_group_that_actually_blocks():
    # A permissive wildcard and an explicit group that blocks GPTBot on purpose.
    # The advice must name the group's own rule, not tell the author to relax a
    # wildcard that was never in the way.
    advice = "\n".join(
        recommendations("User-agent: *\nAllow: /\n\nUser-agent: GPTBot\nDisallow: /\n")
    )
    assert "GPTBot" in advice
    assert "Relax the wildcard" not in advice


def test_audit_policy_note_does_not_claim_the_crawler_is_not_reading_the_site():
    rows = audit_policy("User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\n")
    name, state, note = next(r for r in rows if r[0] == "GPTBot")
    assert state == "allowed"
    assert "cannot read you" not in note
    assert "probably want" not in note
