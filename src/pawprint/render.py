"""Render ``llms.txt`` and ``llms-full.txt`` per the llmstxt.org v2 spec.

The index file (``llms.txt``) is a curated markdown map: an H1, a blockquote
summary, then a section of links. The full file (``llms-full.txt``) is the
complete text, for engines that want everything rather than a map.
"""

from __future__ import annotations

from .content import Page, PageSet, all_text, lead_page, site_name, summarise

SPEC_URL = "https://llmstxt.org/"


def render_index(pages: PageSet, *, name: str | None = None, base_url: str = "") -> str:
    """Render the ``llms.txt`` index.

    Args:
        pages: Parsed content tree.
        name: Site name. Defaults to the first top-level page title.
        base_url: Optional origin prefix (``https://example.com``) so links are
            absolute. Empty means links stay site-relative.
    """
    title = name or site_name(pages.pages)
    lines: list[str] = [f"# {title}", ""]

    lead = lead_page(pages.pages)
    if lead is not None:
        blurb = summarise(lead, limit=300)
        if blurb:
            lines.extend([f"> {blurb}", ""])

    lines.append("This file is a map of the site, for AI agents that want to read")
    lines.append("the whole thing without guessing at URLs. Each entry links to a page")
    lines.append("and gives one line on what is there.")
    lines.append("")

    if not pages.pages:
        lines.extend(["## Pages", "", "_(no content pages found)_", ""])
        return "\n".join(lines)

    for section, group in _group_by_section(pages):
        lines.append(f"## {section}")
        lines.append("")
        for page in group:
            link = _link(page, base_url)
            summary = summarise(page, limit=160)
            if summary:
                lines.append(f"- [{page.title}]({link}): {summary}")
            else:
                lines.append(f"- [{page.title}]({link})")
        lines.append("")

    lines.append("## Optional")
    lines.append("")
    lines.append(f"- [Full text]({_abs('llms-full.txt', base_url)}): every page in one file.")
    lines.append(f"- [Spec]({SPEC_URL}): what this format is and why it exists.")
    lines.append("")

    return "\n".join(lines)


def render_full(pages: PageSet, *, name: str | None = None) -> str:
    """Render ``llms-full.txt``: the complete text of every page."""
    title = name or site_name(pages.pages)
    header = f"# {title}\n\nFull text of every page on this site, for AI agents."
    if not pages.pages:
        return header + "\n\n_(no content pages found)_\n"
    return header + "\n\n" + all_text(pages.pages) + "\n"


def _group_by_section(pages: PageSet) -> list[tuple[str, list[Page]]]:
    """Bucket pages by their top-level path segment, or 'Pages' at the root."""
    buckets: dict[str, list[Page]] = {}
    for page in pages.pages:
        if "/" in page.rel_path:
            key = page.rel_path.split("/", 1)[0]
        else:
            key = "Pages"
        buckets.setdefault(key, []).append(page)
    ordered = []
    if "Pages" in buckets:
        ordered.append(("Pages", buckets.pop("Pages")))
    for key in sorted(buckets):
        pretty = key.replace("-", " ").replace("_", " ").title()
        ordered.append((pretty, buckets[key]))
    return ordered


def _abs(path: str, base_url: str) -> str:
    if not base_url:
        return path
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _link(page: Page, base_url: str) -> str:
    """Render one page's link.

    Site-relative links keep their leading slash so they are valid from any
    page depth. The homepage (``/``) is a bare origin, not an empty string,
    because ``[Docs]()`` is not a link at all.
    """
    path = page.url
    if not base_url:
        return path
    return _abs(path, base_url)
