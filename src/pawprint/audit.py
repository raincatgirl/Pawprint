"""Readiness audit: score how legible a site is to an AI engine.

Five checks, each worth 20 points, so the score is legible rather than
precise. The point is the report, not the number.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .content import PageSet, plain_text
from .render import SPEC_URL

# Files that make a site agent-legible, and where they usually live.
CANDIDATE_FILES = ("llms.txt", "llms-full.txt", "robots.txt", "sitemap.xml")

_LINK_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^>\s+.+", re.MULTILINE)
_WORD_RE = re.compile(r"[A-Za-z一-鿿]")


@dataclass(frozen=True)
class Check:
    """One audit result line."""

    name: str
    passed: bool
    detail: str
    points: int = 20


def _has_ai_crawler_rule(robots_text: str) -> bool:
    """True when robots.txt names at least one known AI crawler in a group.

    This used to be a substring scan over the whole file, which reported a
    crawler as "named" anywhere the string appeared — including in a comment,
    in a ``Sitemap:`` URL, and in a ``Disallow:`` path. A file of

        User-agent: *
        Allow: /

        Sitemap: https://example.com/sitemap-gptbot.xml

    says nothing at all about GPTBot, and scored the full 20 points anyway. So
    did a file whose only mention was ``# TODO: decide about GPTBot``. The
    audit then told the reader their site had an explicit crawler policy when
    it had none, which is the single fact check 2 exists to establish.

    ``parse_robots`` already reads groups properly, and already strips
    comments, so asking it is both correct and a reuse rather than a third
    opinion on what a robots.txt means. A wildcard alone does not count: the
    check asks whether an AI crawler was named, and ``*`` names no crawler.
    """
    from .crawlers import CRAWLERS, parse_robots

    groups = parse_robots(robots_text).get("groups") or {}
    return any(c.name.lower() in groups for c in CRAWLERS)


def run_checks(root: str, pages: PageSet) -> list[Check]:
    """Run the five checks against a content root."""
    checks: list[Check] = []

    # 1. Does an index file exist at all?
    has_llms = os.path.exists(os.path.join(root, "llms.txt"))
    checks.append(
        Check(
            "llms.txt present",
            has_llms,
            "found" if has_llms else "missing — run `pawprint build`",
        )
    )

    # 2. Crawler policy names at least one AI crawler.
    robots_path = os.path.join(root, "robots.txt")
    robots_text = ""
    if os.path.exists(robots_path):
        try:
            with open(robots_path, "r", encoding="utf-8") as handle:
                robots_text = handle.read()
        except (OSError, UnicodeDecodeError):
            robots_text = ""
    if robots_text:
        named = _has_ai_crawler_rule(robots_text)
        checks.append(
            Check(
                "robots.txt names AI crawlers",
                named,
                "yes" if named else "no AI crawler rules found — crawlers fall back to the wildcard",
            )
        )
    else:
        checks.append(Check("robots.txt present", False, "missing — crawlers get no explicit policy"))

    # 3. A sitemap exists so crawlers do not have to guess URLs.
    has_sitemap = any(
        os.path.exists(os.path.join(root, name)) for name in ("sitemap.xml", "sitemap.txt")
    )
    checks.append(
        Check(
            "sitemap present",
            has_sitemap,
            "found" if has_sitemap else "missing — crawlers must infer URLs from links",
        )
    )

    # 4. Content depth: is there enough text to be worth citing?
    words = sum(len(_WORD_RE.findall(plain_text(page.body))) for page in pages)
    if words == 0:
        checks.append(Check("content depth", False, "no indexable text found"))
    elif words < 300:
        checks.append(Check("content depth", False, f"{words} words — too thin to be cited"))
    elif words < 3000:
        checks.append(Check("content depth", True, f"{words} words"))
    else:
        checks.append(Check("content depth", True, f"{words} words — substantial"))

    # 5. Are the pages self-describing? (title + description on most of them)
    if pages.pages:
        described = sum(1 for page in pages.pages if page.description)
        ratio = described / len(pages.pages)
        if ratio >= 0.8:
            checks.append(Check("page descriptions", True, f"{described}/{len(pages.pages)} pages have one"))
        elif ratio >= 0.4:
            checks.append(Check("page descriptions", False, f"only {described}/{len(pages.pages)} pages have one"))
        else:
            checks.append(Check("page descriptions", False, f"{described}/{len(pages.pages)} pages have one — add `description:` to front matter"))
    else:
        checks.append(Check("page descriptions", False, "no pages to describe"))

    return checks


def score(checks: list[Check]) -> int:
    """Sum of the passed checks' points, 0-100."""
    return sum(c.points for c in checks if c.passed)


def grade(value: int) -> str:
    """A short, honest label for a score."""
    if value >= 80:
        return "good"
    if value >= 60:
        return "workable"
    if value >= 40:
        return "patchy"
    if value > 0:
        return "barely legible"
    return "invisible to AI engines"


def summarise(checks: list[Check], pages: PageSet) -> str:
    """Human-readable report."""
    total = score(checks)
    lines = [
        f"AI-readiness: {total}/100 ({grade(total)})",
        f"Pages: {len(pages)}",
        "",
    ]
    width = max((len(c.name) for c in checks), default=0)
    for check in checks:
        mark = "PASS" if check.passed else "FAIL"
        lines.append(f"  [{mark}] {check.name.ljust(width)}  {check.detail}")
    lines.append("")
    failing = [c for c in checks if not c.passed]
    if failing:
        lines.append("Next steps:")
        for check in failing:
            lines.append(f"  - {check.name}: {check.detail}")
    else:
        lines.append("Nothing to fix. Ship it.")
    lines.append("")
    lines.append(f"Format spec: {SPEC_URL}")
    return "\n".join(lines)
