"""AI-crawler policy: who is allowed to read the site, and what is missing.

Pawprint ships a table of the crawlers that actually matter for generative
answer engines. Everything here is static knowledge, so ``policy`` works with
no network access at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ROBOTS_SAMPLE = """User-agent: *
Allow: /

User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

Sitemap: https://example.com/sitemap.xml
"""


@dataclass(frozen=True)
class Crawler:
    """One AI crawler and why a site might want it blocked or allowed."""

    name: str
    purpose: str
    want_allowed: bool


CRAWLERS: tuple[Crawler, ...] = (
    Crawler("GPTBot", "OpenAI training + ChatGPT live crawl", True),
    Crawler("OAI-SearchBot", "ChatGPT search results (citation source)", True),
    Crawler("ChatGPT-User", "User-triggered fetches when a user chats", True),
    Crawler("ClaudeBot", "Anthropic crawler", True),
    Crawler("Claude-User", "Anthropic user-triggered fetch", True),
    Crawler("Claude-SearchBot", "Anthropic search / citations", True),
    Crawler("PerplexityBot", "Perplexity index and answers", True),
    Crawler("Google-Extended", "Gemini training and grounding", False),
    Crawler("Applebot-Extended", "Apple Intelligence training", False),
    Crawler("meta-externalagent", "Meta AI crawler", False),
    Crawler("Bytespider", "ByteDance crawler", False),
    Crawler("CCBot", "Common Crawl, the upstream of many training sets", False),
    Crawler("cohere-ai", "Cohere training", False),
    Crawler("Diffbot", "Third-party data extraction", False),
)


_DIRECTIVE_RE = re.compile(r"user-agent\s*:\s*(\S+)", re.IGNORECASE)
_ALLOW_RE = re.compile(r"^\s*allow\s*:\s*(\S+)", re.IGNORECASE)
_DISALLOW_RE = re.compile(r"^\s*disallow\s*:\s*(\S*)", re.IGNORECASE)
_SITEMAP_RE = re.compile(r"^\s*sitemap\s*:\s*(\S+)", re.IGNORECASE)


def parse_robots(text: str) -> dict[str, object]:
    """Parse a robots.txt into a minimal, useful shape.

    Returns a dict with ``groups`` (mapping user-agent -> list of
    ``(allow, disallow)`` tuples), ``sitemaps``, and ``unreachable`` (the set of
    crawlers from :data:`CRAWLERS` that no group names).
    """
    groups: dict[str, list[tuple[bool, str]]] = {}
    sitemaps: list[str] = []
    current: list[str] = []
    # A group is the run of User-agent lines followed by the rules that apply
    # to them. Once a rule has been seen, the next User-agent line starts a
    # new group, even with no blank line in between (RFC 9309 allows both).
    # Without this, a second group's rules get appended to the first group's
    # members, and a site that blocks GPTBot and allows ClaudeBot reads as
    # "GPTBot: partial" — a claim about a crawler's access that is simply false.
    sealed = False

    for raw in text.split("\n"):
        line = raw.split("#", 1)[0].strip()
        if not line:
            # Blank line after rules closes the group. A blank line between
            # User-agent lines of the same group is not a boundary, so a
            # group still collecting agents stays open.
            if sealed:
                current = []
            continue
        sitemap = _SITEMAP_RE.match(line)
        if sitemap:
            sitemaps.append(sitemap.group(1))
            continue
        agent = _DIRECTIVE_RE.match(line)
        if agent:
            if sealed:
                current = []
            name = agent.group(1).lower()
            if name not in current:
                current.append(name)
                groups.setdefault(name, [])
            continue
        if current:
            allow = _ALLOW_RE.match(line)
            disallow = _DISALLOW_RE.match(line)
            if allow:
                for name in current:
                    groups[name].append((True, allow.group(1)))
            elif disallow:
                for name in current:
                    groups[name].append((False, disallow.group(1)))
            sealed = True

    named = {name.lower() for name in groups}
    unreachable = {c.name for c in CRAWLERS if c.name.lower() not in named}
    return {"groups": groups, "sitemaps": sitemaps, "unreachable": unreachable}


def verdict(crawler: Crawler, robots: dict[str, object]) -> str:
    """One of ``allowed``, ``blocked``, ``unlisted``, or ``partial``."""
    groups = robots.get("groups") or {}
    rules = groups.get(crawler.name.lower())
    if rules is None:
        return "unlisted"
    allows = [path for is_allow, path in rules if is_allow]
    blocks = [path for is_allow, path in rules if not is_allow]
    if not blocks:
        return "allowed" if allows else "unlisted"
    if any(path in ("", "/") for path in blocks):
        return "blocked" if not any(path in ("", "/") for path in allows) else "partial"
    return "partial"


def audit_policy(text: str) -> list[tuple[str, str, str]]:
    """Return ``(crawler, verdict, note)`` for every known AI crawler."""
    robots = parse_robots(text)
    rows: list[tuple[str, str, str]] = []
    for crawler in CRAWLERS:
        state = verdict(crawler, robots)
        if crawler.want_allowed and state in ("blocked", "unlisted"):
            note = "You probably want this one reading you."
        elif not crawler.want_allowed and state == "allowed":
            note = "Open to training crawlers; block if you did not mean to."
        elif state == "partial":
            note = "Some paths blocked, some open."
        else:
            note = crawler.purpose
        rows.append((crawler.name, state, note))
    return rows


def recommendations(text: str) -> list[str]:
    """Concrete, ordered fixes for the crawler policy."""
    robots = parse_robots(text)
    out: list[str] = []

    sitemaps = robots.get("sitemaps") or []
    if not sitemaps:
        out.append("No Sitemap: line in robots.txt. Add one so crawlers can find your pages without guessing.")
    elif len(sitemaps) == 1:
        out.append(f"Sitemap declared ({sitemaps[0]}) — good.")
    else:
        out.append(f"{len(sitemaps)} sitemaps declared; that is fine if you really have that many content splits.")

    wanted = [c.name for c in CRAWLERS if c.want_allowed and verdict(c, robots) in ("blocked", "unlisted")]
    if wanted:
        out.append(
            "Not reading you (blocked or unlisted): " + ", ".join(wanted) + ". "
            "Add an explicit `User-agent:` group for each if you want to be cited."
        )
    else:
        out.append("All citation-relevant crawlers are allowed — good.")

    training = [c.name for c in CRAWLERS if not c.want_allowed and verdict(c, robots) == "allowed"]
    if training:
        out.append(
            "Training crawlers currently allowed: " + ", ".join(training) + ". "
            "Add `Disallow: /` for each if you want your content out of training sets."
        )
    return out
