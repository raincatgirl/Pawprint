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

# CJK ideographs, which are words in their own right: Chinese and Japanese put
# no space between them, so they cannot be counted as runs the way Latin text
# is. The ranges are the Unified Ideographs blocks plus the compatibility
# ideographs, so rarer characters in those planes are not missed.
_CJK = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ffff"

# One character of a run-based word: a word character that is neither an
# ideograph nor a joiner. `[^\W...]` is "a word character, except these", since
# `\W` is the negation of `\w` and the class subtracts from it. The joiners are
# excluded here so they can only ever appear *between* two word characters,
# which is what keeps a standalone dash in "a - b" from being a word.
_WORD_CHAR = r"[^\W" + _CJK + r"-'\u2019]"

# A run of word characters, optionally joined by a hyphen or an apostrophe, so
# `well-known`, `self-contained` and `It's` are one word each — which is what a
# word processor reports, and what the threshold in the report is compared
# against. The lookahead demands at least one real word character, so a lone
# `-` or `'`, or a trailing hyphen, starts nothing.
_WORD_RE = re.compile(
    r"(?=" + _WORD_CHAR + r")"
    + _WORD_CHAR
    + r"+(?:[-\u2019']" + _WORD_CHAR + r"+)*"
    + r"|[" + _CJK + r"]"
)


def count_words(text: str) -> int:
    """Count the words in ``text``.

    This used to be a single-character class applied with ``findall``, which
    returns one match per *character* rather than per word. Ordinary English
    prose therefore came out at roughly four times its real length, and a page
    of 74 words reported itself as 301 — comfortably past the "thick enough to
    be worth citing" bar, which is what check 4 exists to enforce. The number
    appears in the report, so it was a number the author could put into a word
    processor and find wrong by a factor of four.

    The character class was not gratuitous: counting runs of Latin characters
    reads most of a Chinese or Japanese page as one enormous word, which is the
    opposite failure. So both are counted in one pass — a run of word
    characters is one word, and an ideograph is one word.
    """
    return len(_WORD_RE.findall(text))



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
    words = sum(count_words(plain_text(page.body)) for page in pages)
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
