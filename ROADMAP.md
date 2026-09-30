# Roadmap

Pawprint is deliberately small. One rule: **every feature must make a site more
readable to an AI engine, or more honest about who is reading it.**

## Shipped (v0.1.0)

- [x] `pawprint build` — generate `llms.txt` + `llms-full.txt` from a content tree
- [x] `build --check` — exit non-zero when the generated files are stale, so CI enforces them
- [x] `pawprint audit` — five-check AI-readiness score with a written report
- [x] `pawprint policy` — which AI crawlers you allow or block, and why
- [x] Zero dependencies, Python 3.9+

## Next

### v0.2 — make the audit actionable
- [ ] `pawprint fix` — read the audit output, write the missing files
      (`llms.txt`, `robots.txt` skeleton) instead of only describing them
- [ ] `pawprint diff OLD NEW` — what changed between two `llms.txt` revisions,
      so a CI job can flag accidental removals from the index

### v0.3 — other content formats
- [ ] AsciiDoc / reStructuredText readers, same `Page` shape
- [ ] HTML directory input: extract `<h1>` and `<meta name="description">`
      from a built site, so Pawprint can post-process its own output

### v1.0 — measurement
- [ ] `pawprint probe` — query a configured AI endpoint for a set of prompts
      and record whether the site gets cited. This is the part every existing
      tool charges for; it stays offline unless you point it at an endpoint.
- [ ] Citation log format: append-only JSONL, so history is diffable

## Deliberately not doing

- **Hosting it as a service.** The whole point is that it runs on your machine.
- **A plugin framework.** Integration is `pawprint build && cp dist/llms.txt .`
- **Framework-specific adapters.** It reads a directory of Markdown. If your
  framework can emit Markdown, it already works.

## Design notes

- **Pure stdlib, permanently.** A tool that needs a package manager to tell you
  whether your site is legible is a tool nobody runs. If a feature needs a
  dependency, it needs a very good reason.
- **Offline by default.** Nothing in `build`, `audit`, or `policy` touches the
  network. The crawler table is static knowledge, not a lookup.
- **Scores are legible, not precise.** Five checks worth 20 points each. The
  report matters; the number is a handle for it.
- **No telemetry, ever.**

## Tick log

- **2026-09-30** — Bug fix, no new flags. The `llms.txt` summary was emitted
  as raw markdown source: `summarise` cut the first prose paragraph and passed
  it through untouched, so emphasis markers, code ticks and link syntax reached
  the index verbatim. In its worst form the entry read
  `- [API](/docs/api): ... see [docs](https://x.test).` — a second link nested
  inside the entry's own link text, which most renderers drop, taking the URL
  with them. The summary now goes through the `plain_text` the audit's word
  count already used, so the two agree on what a page says. One existing test
  had pinned the defect (it asserted ``The `get` method``); its intent was
  "prose under a fence is found", which still holds. Suite: 224 passing, up
  from 216. Found by reading `summarise`.

- **2026-10-24** — Bug fix, no new flags. `is_index_path` compared the filename
  to `index.md` case-sensitively while the walker collects content suffixes
  case-insensitively, so `docs/Index.md` was read into the tree and then linked
  at `/docs/Index` — a URL that 404s on a real static site — and a site whose
  homepage was `Index.md` was named after a sibling page. Found by reading
  `is_index_path` against `_walk`.
- **2026-10-23** — Bug fix, no new flags. A fenced code block ends at its
  closing fence and the next line starts a fresh block, but blocks were split
  on blank lines alone, so prose written directly under a fence was glued onto
  the fence's own block and skipped as code. A page that opened with an install
  snippet produced no summary at all, and its `llms.txt` line was a bare link
  with nothing after it. A `~~~` fence leaked the opposite way: tildes were
  never in the list of block-opening line prefixes, so a tilde-fenced block was
  read as prose and the index line read `~~~ pip install acme ~~~ Run this
  once...`. Found by reading `_first_prose_paragraph`. Suite: 204 passing, up
  from 197.

- **2026-10-22** — Bug fix, no new flags. The content-depth check counted
  characters, not words: `_WORD_RE` was a single-character class applied with
  `findall`, so ordinary English prose reported at roughly four times its real
  length and the 300-word "thick enough to cite" bar was crossed at about 74
  real words. A thin page scored the full 20 points, and the report printed a
  number the author could check in a word processor and find wrong by four
  times. `count_words` now counts a run of word characters as one word and an
  ideograph as one word, so CJK is still counted rather than read as one
  enormous word. Suite: 197 passing, up from 182.
- **2026-10-21** — Bug fix, no new flags. Audit check 2 decided whether
  robots.txt named an AI crawler by scanning the whole file for the crawler's
  name as a substring, so a mention in a comment, in a `Sitemap:` URL, or in a
  `Disallow:` path scored the full 20 points. A site that said nothing about
  any crawler was reported as having an explicit crawler policy. The check now
  asks `parse_robots`, which already reads groups and strips comments. Suite:
  182 passing, up from 177.
- **2026-10-20** — The 2026-10-19 tick's parser change was never committed; it
  landed the nine tests and left them red, so `main` failed for a day. Fixed
  here rather than shipped over. A blank line now ends a robots.txt group
  whether or not the group stated a rule, per RFC 9309's
  `*(ruleline / emptyline)`. Suite: 177 passing, up from 168.
- **2026-10-19** — Bug fix, no new flags. The empty-group rule from the
  previous tick was written into the named-agent branch and so never applied
  to the wildcard. A robots.txt that says only `User-agent: *` was reported
  as `unlisted`, and the recommendations claimed the wildcard "is closed to
  citation crawlers" and advised relaxing a `Disallow` that was not in the
  file. Found by reading `verdict`.
- **2026-10-18** — Bug fix, no new flags. A group that names a crawler and then
  states no rules was read as though no group named it, so
  `User-agent: *` + `Disallow: /` + `User-agent: GPTBot` — the ordinary way to
  opt one crawler in — reported GPTBot as blocked and advised the author to
  relax a wildcard they had already correctly overridden. `pawprint policy`
  was making a false claim about who can read the site, in the direction that
  hides an open door. Found by reading `verdict`.
- **2026-10-17** — Bug fix, no new flags. An ATX heading may be closed by its
  own run of hashes, and that closing sequence was being read as part of the
  title, so `# Setup ##` produced a page titled `Setup ##` and an index line
  quoting markup as content. A title that is seven hashes long was also read as
  a heading, which is a paragraph. Found by reading `_H1_RE`.
- **2026-10-16** — Bug fix, no new flags. CommonMark has two ways to write an
  H1 and only the ATX `# ` one was read. A page written as `Getting Started`
  over a `===============` underline was titled after its filename, and its
  index summary was the literal underline. Found by reading `_first_h1`.
- **2026-10-15** — Bug fix, no new flags. The fallback H1 was found with a
  bare regex, which read straight through fenced code blocks, so a page whose
  first heading was a shell comment was titled after the comment and linked
  under it in `llms.txt`. Found by reading `parse_page`.
- **2026-10-14** — Bug fix, no new flags. `verdict` never fell back to the
  `User-agent: *` group, so the most common robots.txt shape on the web was
  read as if it named nobody: a site with `* / Disallow: /` was told every AI
  crawler was merely "unlisted" and that the fix was to add a group for each
  one. A blank `Disallow:` was also stored as a block of the whole site, when
  RFC 9309 reads it as an allow. Found by reading `verdict`.
- **2026-10-13** — Bug fix, no new flags. `parse_robots` never closed a
  group, so every rule in the file after the first `User-agent:` line was
  applied to every agent named in it. A robots.txt that blocked GPTBot and
  allowed ClaudeBot reported GPTBot as "partial" instead of "blocked", and
  reported ClaudeBot as reading a `Disallow: /` it never had. `pawprint policy`
  was making confident, false statements about who can read a site. Found by
  reading `parse_robots`.
- **2026-10-12** — Bug fix, no new flags. `plain_text` stripped backticks with
  a pattern anchored to the start and end of the *line*, so a sentence with two
  inline code spans came out as ``a` and `b``. The audit's word count reads
  that text, so sites were being undercounted on check 4. Found by reading
  `plain_text`.
- **2026-10-11** — Bug fix, no new flags. `plain_text` turned `__init__`
  into `init` and `__name__` into `name`, because the emphasis-stripper's
  word-boundary guard did not count `_` as an identifier character. Found by
  reading `_EMPHASIS_RE`.
- **2026-10-10** — Bug fix, no new flags. `index.markdown` was collected but
  never recognised as a homepage, so it was linked at `/index` and the site
  was named after a sibling page. Found by reading `Page.url`.
- **2026-10-09** — Bug fix, no new flags. `plain_text` was deleting the
  underscores out of `snake_case` identifiers, because the emphasis stripper
  had no word boundaries. Found by reading `plain_text`.
- **2026-10-08** — Bug fix, no new flags. The `llms.txt` H1 is taken from
  `index.md`, not from whichever root-level page sorted first. A site with a
  `changelog.md` was named "Changelog".
- **2026-10-07** — Bug fix, no new flags. Indented code blocks are no longer
  used as `llms.txt` summaries. Found by reading `_first_prose_paragraph`.
- **2026-10-06** — `build --check` shipped. Exit code, not a warning.

