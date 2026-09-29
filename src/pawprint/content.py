"""Content-tree discovery and markdown front-matter parsing.

Pawprint never needs a YAML parser: it reads the small, well-defined subset of
front matter that shows up in static-site content files, using stdlib only.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Iterable, Iterator

# Files we will read as content sources. Anything else in the tree is ignored.
CONTENT_SUFFIXES = (".md", ".markdown")

# Directories that never contain site content worth indexing.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".next",
        ".cache",
        "vendor",
        "target",
        "site-packages",
    }
)

_FM_DELIM = "---"
_TITLE_RE = re.compile(r"^title\s*:\s*(.+?)\s*$")
_DESC_RE = re.compile(r"^description\s*:\s*(.+?)\s*$")
_ORDER_RE = re.compile(r"^order\s*:\s*(\d+)\s*$")
_DRAFT_RE = re.compile(r"^draft\s*:\s*(true|false)\s*$", re.IGNORECASE)
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Page:
    """One content file, parsed.

    Attributes:
        path: Absolute path to the source file.
        rel_path: Path relative to the content root, using forward slashes.
        title: Front-matter ``title`` if present, else the first H1, else the
            file stem with dashes turned into spaces.
        description: Front-matter ``description`` if present, else empty.
        order: Front-matter ``order`` if present, else ``None``.
        body: Markdown body with front matter stripped.
        is_draft: True when front matter sets ``draft: true``.
    """

    path: str
    rel_path: str
    title: str
    description: str
    order: int | None
    body: str
    is_draft: bool

    @property
    def url(self) -> str:
        """Best-effort public URL path for this page.

        ``docs/guide.md`` -> ``/docs/guide``; ``index.md`` -> ``/``;
        ``docs/index.md`` -> ``/docs/``; ``README.md`` -> ``/README``.
        """
        if self.rel_path.endswith("/index.md") or self.rel_path == "index.md":
            parent = self.rel_path.rsplit("/", 1)[0] if "/" in self.rel_path else ""
            return "/" + (parent + "/" if parent else "")
        return "/" + self.rel_path.rsplit(".", 1)[0]


@dataclass
class PageSet:
    """A parsed content tree."""

    root: str
    pages: list[Page] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.pages)

    def __iter__(self) -> Iterator[Page]:
        return iter(self.pages)


def parse_front_matter(text: str) -> tuple[dict[str, object], str]:
    """Split leading ``---`` front matter from the markdown body.

    Tolerates a missing or unterminated block, in which case the whole text is
    the body and the metadata mapping is empty.
    """
    if not text.startswith(_FM_DELIM):
        return {}, text

    lines = text.split("\n")
    if not lines or lines[0].strip() != _FM_DELIM:
        return {}, text

    for index in range(1, len(lines)):
        if lines[index].strip() == _FM_DELIM:
            meta = _parse_meta_block(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            return meta, body.lstrip("\n")

    # Unterminated block: treat the whole file as body rather than guessing.
    return {}, text


def _parse_meta_block(lines: list[str]) -> dict[str, object]:
    meta: dict[str, object] = {}
    for raw in lines:
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        match = _TITLE_RE.match(f"{key}: {value}")
        if match:
            meta["title"] = match.group(1).strip().strip("\"'")
            continue
        match = _DESC_RE.match(f"{key}: {value}")
        if match:
            meta["description"] = match.group(1).strip().strip("\"'")
            continue
        match = _ORDER_RE.match(f"{key}: {value}")
        if match:
            meta["order"] = int(match.group(1))
            continue
        match = _DRAFT_RE.match(f"{key}: {value}")
        if match:
            meta["draft"] = match.group(1).lower() == "true"
            continue
    return meta


def parse_page(path: str, rel_path: str, text: str) -> Page:
    """Build a :class:`Page` from raw file text."""
    meta, body = parse_front_matter(text)

    title = meta.get("title")
    if not isinstance(title, str) or not title:
        h1 = _H1_RE.search(body)
        title = h1.group(1).strip() if h1 else rel_path.rsplit("/", 1)[-1].rsplit(".", 1)[0].replace("-", " ").replace("_", " ")

    description = meta.get("description")
    if not isinstance(description, str):
        description = ""

    order = meta.get("order")
    if not isinstance(order, int):
        order = None

    is_draft = meta.get("draft") is True

    return Page(
        path=path,
        rel_path=rel_path,
        title=title.strip(),
        description=description.strip(),
        order=order,
        body=body,
        is_draft=is_draft,
    )


def _walk(root: str) -> Iterator[tuple[str, str]]:
    """Yield ``(absolute_path, relative_path)`` for content files under root."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for filename in sorted(filenames):
            if filename.startswith("."):
                continue
            if not filename.lower().endswith(CONTENT_SUFFIXES):
                continue
            abs_path = os.path.join(dirpath, filename)
            rel = os.path.relpath(abs_path, root).replace(os.sep, "/")
            yield abs_path, rel


def _sort_key(page: Page) -> tuple[int, str]:
    """Explicit ``order`` first (ascending), then path.

    Pages without an explicit order all share ``order=0`` so they sort by path
    rather than being pushed behind every numbered page.
    """
    return (page.order if page.order is not None else 0, page.rel_path)


def collect(root: str, *, include_drafts: bool = False) -> PageSet:
    """Read every content file under ``root`` into a sorted :class:`PageSet`."""
    pages: list[Page] = []
    for abs_path, rel in _walk(root):
        try:
            with open(abs_path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except (OSError, UnicodeDecodeError):
            continue
        page = parse_page(abs_path, rel, text)
        if page.is_draft and not include_drafts:
            continue
        pages.append(page)
    pages.sort(key=_sort_key)
    return PageSet(root=root, pages=pages)


def plain_text(markdown: str) -> str:
    """Strip the markdown decorations an LLM does not need.

    Keeps link targets (they are often the only place a URL appears) but drops
    emphasis markers, heading hashes, and image syntax.
    """
    out: list[str] = []
    for line in markdown.split("\n"):
        line = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"\[([^\]]*)\]\(([^)]*)\)", r"\1 (\2)", line)
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^>\s?", "", line)
        line = re.sub(r"[*_]{1,3}", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "- ", line)
        line = re.sub(r"^`{1,3}|`{1,3}$", "", line.strip())
        out.append(line.rstrip())
    return "\n".join(out).strip()


def summarise(page: Page, limit: int = 200) -> str:
    """A short one-paragraph description for the index file.

    Prefers front-matter ``description``; otherwise takes the first real prose
    paragraph of the body, skipping headings, list bullets, tables, and fenced
    code. Truncated to ``limit`` characters on a word boundary.
    """
    if page.description:
        return page.description
    paragraph = _first_prose_paragraph(page.body)
    paragraph = " ".join(paragraph.split())
    if not paragraph:
        return ""
    if len(paragraph) <= limit:
        return paragraph
    cut = paragraph[:limit].rsplit(" ", 1)[0]
    if not cut:
        return paragraph[:limit] + "..."
    return cut + "..."


_SKIP_PREFIXES = ("#", "-", "*", "+", ">", "|", "```", "\t")
_INDENT_RE = re.compile(r"^ {4,}")


def _is_indented_code(line: str) -> bool:
    """True for a line that CommonMark reads as an indented code block.

    An indented code block is 4+ spaces, or a tab, at the start of a line.
    This has to be checked against the *raw* line: stripping the leading
    whitespace first would destroy the very indent being looked for.
    """
    return bool(_INDENT_RE.match(line)) or line.startswith("\t")


def _first_prose_paragraph(body: str) -> str:
    """First block that reads like a sentence rather than structure.

    Works on the raw markdown, not the stripped text, so a one-line paragraph
    is still recognised as prose while a heading is not.
    """
    for block in body.split("\n\n"):
        lines = [line for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if _is_indented_code(lines[0]) or lines[0].lstrip().startswith(_SKIP_PREFIXES):
            continue
        return " ".join(line.strip() for line in lines)
    return ""


def site_name(pages: Iterable[Page], default: str = "This site") -> str:
    """Pick a site name for the H1 of the generated files.

    A root ``index.md`` names the site. Failing that, the first top-level page
    does — but never a nested one, since a directory landing page is not the
    name of the site and "This site" is a better H1 than a sub-section's.

    The old version returned whichever top-level page sorted first, so a site
    with a root-level ``changelog.md`` or ``about.md`` was named after that
    page instead of after its own index.
    """
    pages = list(pages)
    for page in pages:
        if page.rel_path == "index.md":
            return page.title
    for page in pages:
        if "/" not in page.rel_path:
            return page.title
    return default


def lead_page(pages: Iterable[Page]) -> Page | None:
    """The page that best describes the site as a whole.

    A root ``index.md`` is the homepage by convention, so it wins over a
    nested page that happens to sort first alphabetically.
    """
    for page in pages:
        if page.rel_path == "index.md":
            return page
    for page in pages:
        if page.rel_path.endswith("/index.md"):
            return page
    for page in pages:
        return page
    return None


def all_text(pages: Iterable[Page]) -> str:
    """Concatenate every page body, for ``llms-full.txt``."""
    chunks: list[str] = []
    for page in pages:
        chunks.append(f"# {page.title}\n\nSource: {page.url}\n\n{page.body.strip()}")
    return "\n\n---\n\n".join(chunks)
