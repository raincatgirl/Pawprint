# Devlog

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
- No diffing, no CI mode, no HTML input yet. All on the roadmap.
