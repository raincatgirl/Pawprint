# Pawprint 🐾

**Zero-dependency GEO toolkit.** Find out whether AI engines can read, cite, and
understand your site — then fix what they can't.

> *A site nobody's AI mentions is a site nobody visits.*

---

## What it does

| Command | Purpose |
|---|---|
| `pawprint build` | Generate `llms.txt` + `llms-full.txt` from a content tree |
| `pawprint build --check` | CI mode: exit non-zero if the generated files are stale |
| `pawprint audit` | Score AI-readiness: crawl policy, citation surface, structure |
| `pawprint policy` | Show which AI crawlers you allow/block and why |

Pure Python standard library. No pip install. No Node. No API keys. No telemetry.
No network calls unless you point it at a live URL.

---

## Why

`llms.txt` is a proposed standard for telling language models how to use a
website. 22,980 GitHub issues mention it. Roughly 10% of domains have adopted
it. Almost every existing generator is either a hosted SaaS with a signup wall
or a plugin for one specific framework.

Pawprint is the framework-agnostic, zero-install version. Your content is
already in a directory — that's all it needs.

---

## Install

```bash
git clone https://github.com/raincatgirl/Pawprint.git
cd Pawprint
python3 -m pawprint --help
```

That's it. Python 3.9+.

---

## Quick start

```bash
# 1. See what an AI crawler sees right now
pawprint audit docs/

# 2. Generate the files
pawprint build docs/ --out dist/

# 3. Check your crawler policy
pawprint policy

# 4. In CI, fail the build if the generated files drifted
pawprint build docs/ --out dist/ --check
```

Output lands in `dist/llms.txt` and `dist/llms-full.txt`, ready to deploy
alongside your site.

---

## License

MIT
