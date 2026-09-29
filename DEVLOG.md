# Devlog

## 2026-10-07 — indented code is no longer a page summary

### What changed

`_first_prose_paragraph` decided whether a block was structure or prose with
`lines[0].lstrip().startswith(_SKIP_PREFIXES)`, and `_SKIP_PREFIXES` contained
the string `"    "` (four spaces) to mean "indented code block". `lstrip()` runs
before the comparison, so the four spaces it was looking for had already been
removed. That check could never fire, and an indented code block was always
treated as prose.

Tab-indented code had the same bug for the same reason, via the `"\t"` prefix.

### Why it matters

A page that opens with a code sample instead of a sentence got that code
sample as its one-line description in `llms.txt`. Given that this file's
entire job is to be read by an LLM, an entry like

    - [Config](/docs/config): import acme acme.connect("wss://example.com")

is worse than no entry at all: a confident-looking but useless summary. This is
the same class of bug as the "summaries read raw markdown" decision recorded
under v0.1.0 — a strip-then-compare step quietly deleting the signal it was
meant to test.

### The fix

The fix splits two concerns that had been tangled together. Structural markers
that survive `lstrip()` stay in `_SKIP_PREFIXES`; anything whose meaning
depends on leading whitespace is tested against the raw line by a new
`_is_indented_code()`, which matches `^ {4,}` or a leading tab, per CommonMark.

### Tests

Two new, one per indent style. The tab case is kept deliberately: the two
styles travel different branches of the new helper, and tabs are what a fair
amount of real content actually uses.

Suite: 90 → 92.

## 2026-10-06 — `build --check`

### What changed

`pawprint build <root> --check` renders both output files in memory, compares
them byte-for-byte with what is on disk, and exits 1 if either differs. It
never writes a file or creates a directory, so it is safe to run on a working
tree you do not want touched. The failure reason is one of `missing`, `stale`,
or `unreadable`, per file.

### Why

`llms.txt` is a pure function of the content tree. That is the whole design
and it has a consequence worth cashing in: "would rebuilding change this file"
is exactly answerable, so a CI job can enforce the index without a Git diff, a
lockfile, or any knowledge of the content beyond what is already on disk.

The obvious alternative is comparing mtimes, and it is the wrong tool. A fresh
clone, a fresh CI container, and a `git checkout` all give the generated file
a newer mtime than the source with no actual content difference. That approach
fails constantly, and a check people learn to ignore is worse than no check.

The report is a verdict and a command, not a diff. Someone reading a red CI log
needs to know what broke and what to run; the line-by-line delta is what
`git diff` is for, and it is already one command away.

### Tests

Nine new, all in `TestBuildCheck`. They cover the four states (missing, fresh,
stale-by-addition, stale-by-edit), the guarantee that `--check` does not mutate
`llms.txt`, both JSON shapes, `--out` awareness (a check against the wrong
directory must fail), and a plain tree that was never built. The no-write test
is the one that earns its keep — a check mode that quietly rewrites the file
it is checking is a broken check.

Suite: 81 → 90.

## v0.1.0 — 2026-10-05

First cut. Three verbs, one promise: no install, no network, no account.

### What exists

| Module | Responsibility |
|---|---|
| `content.py` | Walk a content tree, parse the front-matter subset, derive URLs and summaries |
| `render.py` | Emit `llms.txt` (curated map) and `llms-full.txt` (complete text) |
| `crawlers.py` | Static table of 15 AI crawlers, robots.txt parser, verdicts, recommendations |
| `audit.py` | Five checks, 20 points each, plus a written report |
| `cli.py` | `build` / `audit` / `policy`, each with a `--json` variant |

### Design decisions worth recording

**URLs keep their directory.** `guide/intro.md` becomes `/guide/intro`, not
`/intro`. An earlier version dropped the directory segment; it was wrong. A
content tree is not a routing table, and pretending otherwise produces links
that 404 the moment a site nests anything.

**The lead page is the root `index.md`, not the first sorted page.** With
`index.md` and `guide/intro.md` on disk, alphabetical order puts `guide/`
first, so the site blurb came from a sub-page. `lead_page()` now looks for a
root index first, then any nested index, then falls back to the first page.

**Summaries read raw markdown, not stripped text.** `plain_text` removes
heading hashes, so a lone `# A` heading becomes the line `A` and gets picked
up as prose — producing entries that read `- [A](a): A`. `_first_prose_paragraph`
inspects the raw block and skips anything starting with a heading, bullet, or
table marker.

**Site-relative links keep their leading slash.** `page.url.lstrip("/")` was
turning `/guide/intro` into `guide/intro`, which resolves relative to the
current page and breaks from any depth. The homepage needed special handling
too: `[Docs]()` is not a link, so `/` is emitted as-is.

**The crawler table is static knowledge.** Fifteen entries covering training
crawlers, search/citation crawlers, and user-triggered fetches. Each is tagged
with whether you generally *want* it reading you — which is what makes
`policy` useful rather than just descriptive. Verdicts are `allowed`,
`blocked`, `partial`, or `unlisted`.

### Tests

81 tests, no mocks, no network. The suite builds real temp directories and
checks real files. The CLI tests call `main()` and parse its stdout.

One test earns its keep: `test_perfect_site_scores_100` constructs a site
that passes all five checks. If a future check is added without a way to
satisfy it, that test fails and the scoring stays honest.

### Known limits

- Front-matter parsing covers `title`, `description`, `order`, `draft`. Anything
  else in the block is ignored rather than erroring, which is the right default
  for a tool meant to run on other people's content.
- `sitemap.xml` detection is presence-only. Pawprint does not parse or
  validate sitemaps; a site can pass the check with a broken sitemap.
- URL derivation assumes a file-extension-stripped mapping. Sites that rewrite
  URLs (`/guide/intro/` with a trailing slash, or extensionless via a router)
  will need `--base-url` plus a manual mapping.
- No diffing and no HTML input yet. Both on the roadmap.
