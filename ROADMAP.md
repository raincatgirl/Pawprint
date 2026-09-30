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

