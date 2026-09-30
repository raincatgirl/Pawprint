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
_H1_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)

# An ATX heading may be closed by its own run of hashes (``# Title #``), which
# is decoration and not part of the text. The run only closes the heading when
# whitespace comes before it, so ``# C#`` and ``# Hashtag #1`` keep their
# hashes, and it only counts when it is hashes at all, so a trailing ``~~~``
# is content.
_ATX_OPEN_RE = re.compile(r"^ {0,3}#{1,6}(\s|$)")
_ATX_CLOSE_RE = re.compile(r"[ \t]+#+$")


def is_atx_heading(line: str) -> bool:
    """True for a line CommonMark reads as an ATX heading.

    One to six hashes, up to three spaces of indent, then whitespace or the end
    of the line. Seven hashes is a paragraph, and an unindented line that starts
    with a fence is a fence, not a heading.
    """
    if line.startswith("\t") or len(line) - len(line.lstrip(" ")) > 3:
        return False
    return bool(_ATX_OPEN_RE.match(line))

# Any `index` with a content suffix is a landing page, not a page called
# "index". Hardcoding `.md` here meant `index.markdown` — which the walker
# happily collects — was linked at `/index` and never named the site. The
# comparison is case-insensitive because the walker is: it collects by
# `str.lower().endswith(CONTENT_SUFFIXES)`, so `Index.md` is content. Left
# here case-sensitive, the two halves disagreed — a capitalised index was
# read into the tree and then treated as an ordinary page, so it was linked
# at `/Index` instead of `/` and never named the site. On a real site that
# URL 404s, because a generator serving `docs/index.md` serves `/docs/`.
# The rule stays exact on the whole filename, so `Indexing.md` is still a
# page called "Indexing".
_INDEX_STEMS = tuple(f"index{suffix}" for suffix in CONTENT_SUFFIXES)


def is_index_path(rel_path: str) -> bool:
    """True when a relative path names a directory or site landing page."""
    return rel_path.rsplit("/", 1)[-1].lower() in _INDEX_STEMS


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
        Any content suffix counts, so ``index.markdown`` is also ``/``.
        """
        if is_index_path(self.rel_path):
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


def _is_setext_underline(line: str) -> bool:
    """True for a line that underlines a preceding paragraph as a heading.

    CommonMark allows a run of ``=`` or ``-``, any length, with up to three
    spaces of indentation and any trailing whitespace. Four spaces of indent
    would make it an indented code block instead, and a run with an internal
    space (``= =``) underlines nothing.
    """
    body = line.strip(" \t")
    if not body or len(line) - len(line.lstrip(" \t")) > 3:
        return False
    return set(body) <= {"="} or set(body) <= {"-"}


def _heading_block(lines: list[str], start: int) -> list[str] | None:
    """The setext heading's content lines at ``lines[start]``, if there is one.

    A setext heading is a paragraph plus an underline, and the paragraph can
    span more than one line. The lines have to be ones that would be a
    paragraph on their own, so anything that is already a block start (an ATX
    heading, a fence, a list bullet, a block quote, an indented code block)
    rules the underline out, as does a blank line.
    """
    content: list[str] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            break
        # An underline ends the heading it underlines, so it is never part of
        # the heading's own content.
        if index > start and _is_setext_underline(line):
            break
        if index > start and (
            _is_indented_code(line)
            or is_atx_heading(line)
            or _BULLET_RE.match(line)
            or line.lstrip().startswith(_BLOCK_PREFIXES)
        ):
            break
        content.append(line)
        index += 1
    if not content:
        return None
    first = content[0]
    if (
        _is_indented_code(first)
        or is_atx_heading(first)
        or _BULLET_RE.match(first)
        or first.lstrip().startswith(_BLOCK_PREFIXES)
    ):
        return None
    if index >= len(lines) or not _is_setext_underline(lines[index]):
        return None
    return content


def _atx_text(raw: str) -> str:
    """The text of an ATX heading, without its opening or closing hashes."""
    return _ATX_CLOSE_RE.sub("", raw).strip()


def _first_heading(body: str) -> str | None:
    """The document's first heading, ATX or setext, outside any fenced code.

    Setext headings are the other legal way to write an H1 in CommonMark
    (``Title`` underlined with ``===``), and they are common in hand-written
    files. Reading only ATX meant a page written that way fell back to its
    filename for a title, and its index summary came out as the literal
    underline: ``Getting Started ===============``.

    The fence tracking is shared with the ATX case, since a shell transcript
    is full of ``# comment`` lines and can just as easily contain a
    ``Fake Title`` over a ``=======`` run.
    """
    lines = body.split("\n")
    fence: str | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if fence is not None:
            # A closing fence is the same character repeated, nothing else.
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                fence = None
            continue
        # An opening fence is a run of three or more, optionally followed by an
        # info string: ```bash is a fence, ``` alone is a fence.
        run = stripped[: len(stripped) - len(stripped.lstrip("`~"))]
        if len(run) >= 3 and set(run) == {run[0]}:
            fence = run
            continue
        match = _H1_RE.match(line)
        if match and is_atx_heading(line):
            return _atx_text(match.group(1))
        content = _heading_block(lines, index)
        if content is not None:
            return _join_heading(content)
    return None


def _join_heading(content: list[str]) -> str:
    """Flatten a heading's lines into one line of text.

    A heading may span lines, and CommonMark parses the joined text as
    inlines, so emphasis opened on one line and closed on the next is
    emphasis. Reading only the last line gave ``Foo *bar\\nbaz*`` the title
    ``baz*``. The lines are joined with a space, which is what a soft line
    break becomes, and the emphasis is then stripped by the same rules the
    rest of the module uses.
    """
    return _strip_emphasis(" ".join(line.strip() for line in content)).strip()


def parse_page(path: str, rel_path: str, text: str) -> Page:
    """Build a :class:`Page` from raw file text."""
    meta, body = parse_front_matter(text)

    title = meta.get("title")
    if not isinstance(title, str) or not title:
        h1 = _first_heading(body)
        title = h1 if h1 else rel_path.rsplit("/", 1)[-1].rsplit(".", 1)[0].replace("-", " ").replace("_", " ")

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


# Emphasis markers only count when they open or close a word. An underscore
# next to any identifier character is part of that identifier
# (`max_tokens`, `load_user_profile()`), and deleting it corrupts the very
# URLs and API names the plain text exists to preserve. The guard has to
# include `_` itself, since an underscore is neither punctuation before an
# identifier nor a word boundary inside one.
_EMPHASIS_RE = re.compile(
    r"(?<![A-Za-z0-9_])([*_]{1,3})(?=\S)(.+?)(?<=\S)\1(?![A-Za-z0-9_])"
)

# A doubled underscore is the one genuinely ambiguous case. By the letter of
# CommonMark, `__init__` is strong emphasis just as much as `__really__` is,
# because the opening run is preceded by a space and followed by a letter.
# In practice the overwhelmingly common use of `__word__` on a technical site
# is a dunder, and a mangled `__init__` is a wrong fact where `__really__`
# left alone is only a missed decoration. So a doubled run wrapped tight
# around identifier characters is treated as part of the identifier, and
# everything else stays eligible for emphasis stripping.
_DUNDER_RE = re.compile(r"(?<![A-Za-z0-9_])__([A-Za-z0-9_]+)__(?![A-Za-z0-9_])")
_PARK_RE = re.compile("\x00([A-Za-z0-9_]*)\x00")


def _strip_emphasis(line: str) -> str:
    """Remove ``*bold*`` and ``_italic_`` without touching identifiers."""
    if "__" not in line:
        return _EMPHASIS_RE.sub(r"\2", line)
    # Park the dunder's inner name between two NULs so the emphasis pass
    # cannot read its underscores as markers, then restore the real name.
    parked = _DUNDER_RE.sub(lambda m: "\x00" + m.group(1) + "\x00", line)
    return _PARK_RE.sub(r"__\1__", _EMPHASIS_RE.sub(r"\2", parked))


_FENCE_RE = re.compile(r"^(`{3,})[ \t]*(.*)$")

# A single- or double-backtick inline code span. Three or more backticks are a
# fence, not a span, so the run lengths must match and must not run together
# with another backtick (``code ` here`` is not a span).
_CODE_SPAN_RE = re.compile(r"(?<!`)(`{1,2})(?!`)(.+?)(?<!`)\1(?!`)")


def _strip_ticks(line: str) -> str:
    """Remove code fences and inline code spans from one line.

    The old version used ``^`{1,3}|`{1,3}$``, which is anchored to the start
    and the end of the *line*. That only ever worked for a line that was
    nothing but one span: ``Use `a` and `b` `` kept the first span's closing
    tick and the second span's opening tick, and came out as
    ``Use a` and `b ``. The plain text an AI reads had a stray backtick glued
    to words, and any word-counting downstream of it counted garbage.
    """
    stripped = line.strip()
    if stripped.startswith("```"):
        # A fence line: keep the info string (``py``), drop the fence itself.
        match = _FENCE_RE.match(stripped)
        if match:
            return match.group(2).rstrip()
    return _CODE_SPAN_RE.sub(r"\2", line)


def plain_text(markdown: str) -> str:
    """Strip the markdown decorations an LLM does not need.

    Keeps link targets (they are often the only place a URL appears) but drops
    emphasis markers, code ticks, heading hashes, and image syntax.
    """
    out: list[str] = []
    for raw in markdown.split("\n"):
        line = raw
        line = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"\[([^\]]*)\]\(([^)]*)\)", r"\1 (\2)", line)
        line = re.sub(r"^#{1,6}(\s|$)", "", line)
        if is_atx_heading(raw):
            # A closing sequence is decoration, so it goes the same way as the
            # opening one. Only a heading can be closed this way, so a line that
            # merely ends in a hash — ``press Ctrl+##`` — keeps it.
            line = _ATX_CLOSE_RE.sub("", line)
        line = re.sub(r"^>\s?", "", line)
        line = _strip_emphasis(line)
        line = re.sub(r"^\s*[-*+]\s+", "- ", line)
        line = _strip_ticks(line)
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
    # The summary is emitted verbatim as the text of a bullet in llms.txt, so
    # it has to be prose, not the markdown source it was cut from. The reader
    # is an AI engine: emphasis markers and code ticks are noise, and a link
    # left in place nests a second link inside the entry's own link text, which
    # most renderers drop — taking the URL with them.
    #
    # This is the same `plain_text` the audit word count already runs over, so
    # the two agree on what a page says. It had to run before the truncation,
    # not after: the limit is on characters the reader actually sees, and
    # cutting first could leave a summary ending mid-marker.
    paragraph = plain_text(paragraph)
    paragraph = " ".join(paragraph.split())
    if not paragraph:
        return ""
    if len(paragraph) <= limit:
        return paragraph
    cut = paragraph[:limit].rsplit(" ", 1)[0]
    if not cut:
        return paragraph[:limit] + "..."
    return cut + "..."


# Line starts that open a block other than a paragraph, including both fence
# characters. CommonMark allows a fenced block to be opened with `~~~` as well
# as ``` ``` ```, and a line beginning `~~~` is a fence rather than a
# paragraph, so leaving tildes off this list let a fenced block be read as
# prose — the index summary of such a page came out as `~~~ pip install acme`.
_INDENT_RE = re.compile(r"^ {4,}")

# A list bullet is a marker, whitespace, then the item. The whitespace is what
# separates `- item` from `--verbose`, and without it the summary reader wrote
# off any page whose prose opened with a leading hyphen, a plus, a hash, or an
# emphasis run as if it were a list or a heading. CommonMark allows an empty
# list item too (`-` alone), so end-of-line counts as the separator.
_BULLET_RE = re.compile(r"^ {0,3}[-*+]([ \t]|$)")

# Line starts that open a block other than a paragraph, as raw prefixes, for
# the cases where no separator is involved. A setext underline can only follow
# a paragraph, so a line starting with one of these is not heading content
# however it is underlined.
_BLOCK_PREFIXES = (">", "|", "```", "~~~")


def _is_indented_code(line: str) -> bool:
    """True for a line that CommonMark reads as an indented code block.

    An indented code block is 4+ spaces, or a tab, at the start of a line.
    This has to be checked against the *raw* line: stripping the leading
    whitespace first would destroy the very indent being looked for.
    """
    return bool(_INDENT_RE.match(line)) or line.startswith("\t")


def _is_structure(line: str) -> bool:
    """True when a line opens a block that is not a paragraph.

    The list markers need the whitespace that makes a bullet a bullet, and the
    ATX heading needs the same, so neither can be answered by a bare prefix
    test. ``is_atx_heading`` is the same predicate the title reader uses, so
    the two agree on what a heading is.
    """
    if _is_indented_code(line) or is_atx_heading(line):
        return True
    if _BULLET_RE.match(line):
        return True
    return line.lstrip().startswith(_BLOCK_PREFIXES)


def _iter_blocks(body: str) -> Iterator[list[str]]:
    """Split markdown into blocks, on blank lines and on fence boundaries.

    A fenced code block is a block in its own right, and CommonMark does not
    require a blank line after its closing fence — the line following the fence
    opens a fresh block. Splitting on blank lines alone glued the prose under a
    fence onto the fence's own block, so the block opened with a run of
    backticks and the prose underneath it was skipped as if it were more code.
    A page that opened with an install snippet therefore produced no summary at
    all, and its entry in ``llms.txt`` was a bare link with nothing after it.

    Tracking the fence also keeps a fenced block together instead of letting a
    blank line inside the code split it into pieces, each of which might have
    looked like a paragraph.
    """
    block: list[str] = []
    fence: str | None = None

    for line in body.split("\n"):
        stripped = line.strip()
        run = stripped[: len(stripped) - len(stripped.lstrip("`~"))]
        if fence is not None:
            # A closing fence is the same character repeated and at least as
            # long as the one that opened it. Closing it ends the block, and
            # the next line starts a new one.
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                fence = None
                yield block
                block = []
            else:
                block.append(line)
            continue
        if len(run) >= 3 and set(run) == {run[0]}:
            fence = run
            block.append(line)
            continue
        if not line.strip():
            if block:
                yield block
                block = []
            continue
        block.append(line)

    if block:
        yield block


def _first_prose_paragraph(body: str) -> str:
    """First block that reads like a sentence rather than structure.

    Works on the raw markdown, not the stripped text, so a one-line paragraph
    is still recognised as prose while a heading is not. A setext heading is
    a heading too, so its content line and underline are dropped the same way
    an ATX heading is — otherwise the summary of a setext page is its own
    title, underlined.
    """
    for lines in _iter_blocks(body):
        lines = [line for line in lines if line.strip()]
        if not lines:
            continue
        heading = _heading_block(lines, 0)
        if heading is not None:
            # A paragraph opened by a setext heading: keep the lines that
            # follow the underline, which are the prose under the heading.
            rest = lines[len(heading) + 1 :]
            if not rest:
                continue
            return " ".join(line.strip() for line in rest)
        if _is_structure(lines[0]):
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
        if "/" not in page.rel_path and is_index_path(page.rel_path):
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
        if "/" not in page.rel_path and is_index_path(page.rel_path):
            return page
    for page in pages:
        if is_index_path(page.rel_path):
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
