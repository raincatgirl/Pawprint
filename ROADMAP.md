# Roadmap

Pawprint is deliberately small. One rule: **every feature must make a site more
readable to an AI engine, or more honest about who is reading it.**

## Shipped (v0.1.0)

- [x] `pawprint build` — generate `llms.txt` + `llms-full.txt` from a content tree
- [x] `pawprint audit` — five-check AI-readiness score with a written report
- [x] `pawprint policy` — which AI crawlers you allow or block, and why
- [x] Zero dependencies, Python 3.9+

## Next

### v0.2 — make the audit actionable
- [ ] `pawprint fix` — read the audit output, write the missing files
      (`llms.txt`, `robots.txt` skeleton) instead of only describing them
- [ ] `pawprint diff OLD NEW` — what changed between two `llms.txt` revisions,
      so a CI job can flag accidental removals from the index
- [ ] `--check` mode for build: exit non-zero when `llms.txt` is stale relative
      to the content tree, so CI enforces it

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
