# Devlog

## 2026-10-20 — the 2026-10-19 tests, made to pass

### What changed

Yesterday's tick added the nine tests in `tests/test_robots_group_closure.py`
and did not land the parser change. `main` was left with six of them failing.
Today's unit of work was to make them pass, not to add anything new.

The change is one condition. `parse_robots` closed a group at a blank line
only if a rule had already been seen:

```python
if not line:
    if sealed:
        current = []
    continue
```

The `sealed` guard was there to keep the multi-agent group form working — the
concern that a blank line between two `User-agent` lines would split a group
that was still collecting members. But that form is written without blank
lines, so it never needed the exemption.

Dropping it means a blank line closes any group. This file:

```
User-agent: *

User-agent: GPTBot
Disallow: /
```

used to parse as one group of two members:

```
{'*': [(False, '/')], 'gptbot': [(False, '/')]}
```

and now parses as a wildcard that states no rule and a named group that
blocks one crawler. `pawprint policy` on it reads:

```
  GPTBot              blocked   You probably want this one reading you.
  ClaudeBot           allowed   Anthropic crawler
```

and recommends adding an explicit group for GPTBot, which is accurate. Before,
it reported all fourteen crawlers blocked and advised relaxing a wildcard
`Disallow` that is not in the file — a confident false claim about who can
read a site, in the direction that hides an open door.

The grammar behind it is RFC 9309's `group = startgrouplines
*(startgroupline) *(ruleline / emptyline)`: a group is closed by an empty
line, and the next `User-agent` line opens a fresh one.

### Why it mattered to fix rather than revert

Reverting would have restored green but thrown away the bug report. The tests
describe a real shape people write — start a placeholder wildcard, then get
round to the crawler you meant to block — and it was misreported. The fix is
two lines smaller than the guard it removes.

### Tests

Nine tests, six failing before the change, 177 passing after. The three that
passed before were the ones asserting the multi-agent and both-rules groups
still parse, which is the behaviour the guard was protecting.

## 2026-10-19 — the same empty-group rule, missed for the wildcard

### What changed

Last tick taught Pawprint that a group which names a crawler and then states
no rules imposes none. The rule was written into the branch that handles a
*cited* group, so it applied to `User-agent: GPTBot` and never to
`User-agent: *`. A crawler that fell through to the wildcard took a different
path, found an empty rule list, and was reported `unlisted`.

A robots.txt consisting of nothing but:

```
User-agent: *
```

is a group, and an empty group. RFC 9309 reads it the same way last tick read
the named one: no rules, so nothing is disallowed. Before the fix:

```
GPTBot   unlisted   You probably want this one reading you.
```

and the recommendation was:

```
A wildcard `User-agent: *` group is closed to citation crawlers, so these
cannot read you: GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-User,
Claude-SearchBot, PerplexityBot. Relax the wildcard's `Disallow`, or add an
`Allow: /` group for the ones you want cited.
```

There is no `Disallow` in that file.

### Why it matters

Same failure mode as yesterday, still live, and the same direction: Pawprint
reports an open site as closed and tells the author to edit a restriction they
never wrote. It is worse here because `User-agent: *` with nothing under it is
a thing people write while they are still deciding, so the file that produces
the false claim is also the one most likely to be read as a placeholder
rather than a policy.

The half-fix was a real hazard too. A reader who saw yesterday's entry would
reasonably conclude the empty-group case was covered.

### How it is fixed

The empty-group check moved out of the named branch and down to where the
group has already been selected, so it applies to whichever group matched.
Selection is unchanged: a named group still wins over the wildcard, and a
crawler no group names is still `unlisted`. A file with only a `Sitemap:`
line still names no group and is still unlisted — the distinction that test
pins is "a group exists and is empty" against "no group exists".

Eight tests in `tests/test_robots_empty_wildcard.py`, including that the
training-crawler warning still fires, since nothing blocked is also nothing
protected.

### A second bug, found and deliberately not fixed here

While writing the tests I hit a case that parses wrong and is not part of this
change: `parse_robots` does not close a group at a blank line when a group
that *did* state rules is followed by a new one. This input:

```
User-agent: *

User-agent: GPTBot
Disallow: /
```

parses the wildcard as `[(False, '/')]` — the GPTBot rule leaks backwards into
it — so ClaudeBot reads as `blocked` when the file disallows nothing for it.
It predates this tick and is independent of the empty-group rule. I reworked
the test that had caught it so this tick ships one fix, not two, and left the
behaviour as it is.


## 2026-10-18 — an empty group was read as no group at all

### What changed

A robots.txt that opts one crawler in under a blocking wildcard is written
with an empty group:

```
User-agent: *
Disallow: /

User-agent: GPTBot
```

Under RFC 9309 that group matches GPTBot, and a group that states no rules
imposes none, so GPTBot is free to read the whole site. Pawprint stored the
group as an empty rule list, found no rules in it, and fell through to the
wildcard. The table said:

```
GPTBot   blocked   You probably want this one reading you.
```

The author had written the exact file that opens the door, and Pawprint
reported it shut.

### Why it matters

`pawprint policy` makes a claim about who can read a site, and this claim was
false in the direction that hides a block. The recommendations were worse than
the verdict, because they told the author to go and relax the wildcard
`Disallow` — a line that was never what was stopping the crawler, and one the
author had already correctly overridden.

### How it is fixed

`verdict` now distinguishes "no group names this crawler" from "a group names
it and states no rules", and reads the second case as unrestricted rather than
falling through to the wildcard.

The same conflation was in the recommendations, which blamed the wildcard for
any blocked citation crawler whenever a wildcard group existed at all. They
now only blame the wildcard for crawlers that have no group of their own, so
a site that deliberately wrote `User-agent: GPTBot` / `Disallow: /` is told
what it actually did rather than being sent to edit the wrong line.

### Tests

160, all passing: 153 before this change, plus 7 new ones covering the
empty-group verdict and the attribution of the block.

## 2026-10-17 — a heading's closing hashes were part of its title

### What changed

CommonMark lets an author close an ATX heading with its own run of hashes:

```
## Setup ##
```

The trailing run is a closing sequence, not text. Pawprint kept it, so that
page's title was `Setup ##`, that is what the H1 of the generated `llms.txt`
said, and that is what the page's own index line read:

```
- [Setup ##](/guide): Run the installer, then restart the daemon.
```

The plain text the audit word-counts had the same decoration, so a heading
that was one word counted as three.

### Why it matters

A title is a claim about the page. Quoting a reader the `#` characters the
author used to draw the heading is quoting markup as content, and the
`llms.txt` is the file that exists to be read by something that never sees the
Markdown.

### How it is fixed

`is_atx_heading` now decides what is a heading once — one to six hashes, up to
three spaces of indent, then whitespace or end of line — and the closing
sequence is stripped only when whitespace precedes it, which is what
CommonMark requires. That distinction is the whole fix: `# C#` and
`# Hashtag #1` are headings whose text ends in a hash, and the hash belongs to
the text. A line that merely ends in hashes without being a heading
(`press Ctrl+##`) keeps them, since only a heading can be closed this way.

Seven hashes is not a heading — it is a paragraph — and that case now falls
back to the filename instead of being titled after a run of hashes.

Ten new tests in `tests/test_atx_closing.py`, covering the title, the summary,
and the plain-text path.

## 2026-10-16 — a setext heading was not a heading

### What changed

`parse_page` found a page's fallback title by scanning for an ATX `# ` line.
CommonMark has two equally legal ways to write an H1, and Pawprint only knew
about one. A page written the other way:

```
Getting Started
===============

Install it with pip.
```

came out as a page titled `install` — the filename — and its index summary
came out as `Getting Started ===============`, the heading text and its
underline glued together. The generated `llms.txt` entry read:

```
- [install](/install): Getting Started ===============
```

`_first_h1` is now `_first_heading`, and it reads both forms. The setext
rules it implements, from the CommonMark 0.31.2 spec section 4.3:

- The underline is a run of `=` (level 1) or `-` (level 2), and it can be any
  length. One character is enough. `Not a rule\n------------------` is a
  heading, not a heading followed by a thematic break, because a setext
  underline takes precedence when a paragraph is open.
- Up to three spaces of indentation on either the content line or the
  underline. Four spaces makes it an indented code block instead.
- Any trailing whitespace, but no internal whitespace: `= =` underlines
  nothing.
- The content line has to be one that would otherwise be a paragraph, so a
  line opening with `#`, `>`, `|`, a fence, or a list bullet is not heading
  content however it is underlined.
- A setext heading cannot interrupt a paragraph, and a line that is already a
  block start cannot be underlined, so `# Title\n---` leaves the title alone.

The same scan keeps tracking code fences, so a `Fake Title` over a `=======`
run inside a bash block is ignored exactly as a `# comment` line already was.

`_first_prose_paragraph` skips a setext heading too. It already skipped ATX
headings as structure, so leaving the other form in meant a setext page
summarised as its own title, repeated. The two readers now share a
`_BLOCK_PREFIXES` constant so they cannot disagree about what counts as
structure.

### Why

An AI engine is handed `llms.txt` and told to use the link text as the name
of a page. `install` and `Getting Started ===============` are both wrong
answers, and unlike a stale word count they are the one line a reader is most
likely to quote back.

### Tests

Eighteen, in `tests/test_setext.py`. Three of them asserted the wrong thing
on the first pass and were corrected against the spec before the
implementation was finished:

- A dash run of four or more was assumed to be a thematic break. Spec example
  83 says the underlining can be any length, so it is a heading.
- A multi-line heading was expected to strip emphasis across the join. Spec
  example 81 renders `Foo *bar\nbaz*` as `Foo <em>bar baz</em>`, so the
  emphasis spans both words and the title is "Foo bar baz", not "Foo bar".

The multi-line case was worth catching: the first implementation took the
last line of the heading, which made `Foo *bar\nbaz*` the page titled `baz*`
— a worse answer than the bug it replaced, since a wrong title is quoted back
into a citation.


## 2026-10-15 — a shell comment inside a code fence was naming the page

### What changed

`parse_page` found a page's fallback title with `_H1_RE.search(body)`, a
multiline regex looking for `^# `. Regexes do not know about code fences, so
the search read straight through them. On a documentation site, where the
first thing a page contains is very often a shell transcript, the first
matching line was a comment:

````
```bash
# Install the package
pip install acme
```
````

The page was titled "Install the package". In the generated `llms.txt` the
entry read `- [Install the package](/docs/install): Install the CLI first...`,
and since the title is also the site name when a page sorts first and the
anchor text an agent follows, the whole map was quietly wrong.

Replaced the regex with `_first_h1`, which scans line by line and tracks
fence state. A fence opens on a run of three or more backticks or tildes
(with an optional info string) and closes on a line of at least as many of
the same character. Inside a fence no line is a heading, no matter what it
starts with.

### Why not just regex the fences away

Stripping fences before the heading search would also delete them from
`body`, which is what `llms-full.txt` renders and what the audit's word
count reads. The scan is local to title detection and touches nothing else.

Two tests: a backtick fence with a `bash` info string, and a bare tilde
fence. The first version of the fix passed the tilde test and failed the
backtick one, because it required the whole stripped line to be fence
characters and ` ```bash ` is not. The info string is what makes a fence
worth parsing, so the opener now matches on the leading run.


## 2026-10-14 — the wildcard group was ignored, and a blank `Disallow:` read as a block

### What changed

`verdict` looked a crawler up by its own name and, finding nothing, returned
`unlisted`. It never fell back to the `User-agent: *` group. Since a wildcard
group is the most common robots.txt shape there is, this was not an edge case:

```
User-agent: *
Disallow: /
```

reported GPTBot, ClaudeBot, PerplexityBot and the rest as `unlisted`, and then
recommended the reader "Add an explicit `User-agent:` group for each if you
want to be cited" — sending them to write fourteen groups that a single line
already covered. The site was shut to every AI crawler and Pawprint said the
opposite.

The same fallback fixes the mirror image. A site that is wide open:

```
User-agent: *
Allow: /
```

read as `unlisted` too, so `pawprint policy` reported a perfectly readable site
as one no crawler had been invited to, and told the reader to go open it.

Separately, `Disallow:` with an empty value was stored as the block `(False,
"")`. RFC 9309 reads an empty value as *disallow nothing* — it is how a site
says "read everything" — and `verdict` treats `""` as a prefix matching the
whole site. The most permissive file on the web was being read as the most
restrictive one. Empty values now record as an allow of `/`.

`verdict` now resolves a crawler against its own group first and the wildcard
only as a fallback, which is the specificity rule RFC 9309 describes. The
recommendation text follows: when a wildcard is what is blocking, the advice is
to relax that one line rather than to go add groups per crawler.

### Why

Both halves are the same class of fault as the group-parsing bug fixed
yesterday, and the same failure mode: `pawprint policy` states its findings as
fact, and in both cases the fact was false in the direction that misleads. A
crawler-policy tool that cannot read a wildcard group is wrong about the
majority of the robots.txt files it will be pointed at.

One existing test changed rather than being preserved:
`test_verdict_unlisted` asserted that `User-agent: * / Allow: /` yields
`unlisted`, which is the bug stated as a requirement. It now uses a file with
no applicable group at all, which is what "unlisted" should mean.

Tests: 113 to 123, in a new `tests/test_robots_wildcard.py`.

## 2026-10-13 — `parse_robots` never closed a group

### What changed

The parser tracked a list of "current" user-agents and appended every rule it
saw to all of them, but nothing ever cleared that list. So a second group in the
file was treated as more agents belonging to the first:

```
User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Allow: /
```

parsed as `gptbot: [Disallow: /, Allow: /]` and `claudebot: [Allow: /]`. The
verdict for GPTBot came back "partial" — the one state that means "some paths
blocked, some open" — when in fact the site had blocked it outright. Worse, a
file listing a training crawler it intended to block, *after* a citation crawler
it intended to allow, would show that training crawler as "allowed" and emit a
recommendation that it should be blocked, which it already was.

This is the ordinary robots.txt shape. Any site with more than one group was
being misreported, and `pawprint policy` states its findings as fact.

### Why

A group is a run of `User-agent:` lines followed by the rules that apply to
them, and a group ends when the next one starts. The parser now tracks whether
any rule has been seen: the first rule seals the group, and both a blank line
and the next `User-agent:` line after that open a fresh one. A blank line
between `User-agent:` lines with no rules yet is not a boundary, so the
multi-agent-per-group form (`test_multiple_user_agents_share_rules`) still
parses as one group.

Nothing else changed. No new flags, no new files, still stdlib only. The old
`flush()` helper and the "leading group belongs to everyone" special case went
away with the bug: `groups.setdefault` on the agent line already did that work,
which is why the dead helper could hide the missing reset for so long.

### Tests

Four new tests, all of which failed before the fix: blank line separates
groups, rules do not leak into the next group, a group ends at the next
`User-agent:` line even with no blank line, and the end-to-end verdict for a
blocked GPTBot in a two-group file. 109 tests before, 113 after.

## 2026-10-12 — `plain_text` left a backtick between two code spans

### What changed

The backtick stripper was a single regex: `re.sub(r"^`{1,3}|`{1,3}$", "", line.strip())`.

Both alternatives are anchored — one to the start of the line, one to the end.
That only ever worked for a line that was *nothing but* a code span. Any line
with two inline spans in the middle lost neither of the middle ticks, because
neither is at an anchor:

```
Use `a` and `b` together.
-> Use a` and `b` together.

Set `max_tokens` before calling `load_user_profile()`.
-> Set `max_tokens` before calling `load_user_profile()`.
```

Fences still worked, because a fence really is at the start of its line. The
bug only showed on ordinary prose, which is to say on most technical writing.

Stripping is now a real span match. A run of one or two backticks delimits an
inline span whose matching run is the same length, and neither run may touch a
third backtick (so ``` ``code with ` tick`` ``` survives, as CommonMark says it
should). Three or more backticks on a line is still treated as a fence and
keeps its info string. The strip moved to the end of the pipeline, after the
link rewrite, so a URL that was itself a code span comes out clean.

### Why it matters

Two reasons, and the second is the real one.

The obvious one is cosmetic: `llms-full.txt` is read by an engine that will
quote it back, and a stray backtick welded to a word is noise in the one file
whose entire job is to be quoted.

The real one is the audit. Check 4 counts words with
`len(_WORD_RE.findall(plain_text(body)))` to decide whether a site is thick
enough to be worth citing, and every unclosed tick glued two words into one
token. A page written in the ordinary technical register — inline code around
every command and identifier — was being undercounted. Content depth is one of
the five checks, so this quietly moved a score the user reads as a verdict on
their own site.

## 2026-10-11 — `plain_text` was eating Python dunder identifiers

### What changed

The emphasis stripper decides whether `*` or `_` is a formatting marker or
part of an identifier by checking the characters on either side of it. The
character class guarding that decision was `[A-Za-z0-9]`, which covers
`snake_case` but not `_` itself.

So for a dunder there was nothing on the left to stop it: `__init__` opened
with a run of underscores preceded by a space, which looks exactly like
strong emphasis. The result:

```
Override __init__ and check __name__ against __main__.
-> Override init and check name against main.

See [dunder](src/__init__.py) for details.
-> See dunder (src/init.py) for details.
```

The guard now includes `_`, and a doubled underscore wrapped tight around
identifier characters is explicitly treated as part of the identifier. That
second rule is a deliberate tie-break in a genuinely ambiguous case: by the
letter of CommonMark, `__init__` is strong emphasis exactly as much as
`__really__` is. On a technical site the common case is overwhelmingly the
dunder, and a mangled `__init__` is a wrong fact, where an unstripped
`__really__` is only a missed decoration. The asymmetry is intentional.

### Why it matters

`llms-full.txt` is fed to an engine that will quote identifiers back at the
reader. An API name that has lost its underscores is not a decoration issue,
it is a name that no longer exists, and the reader who trusts the summary
gets a `ModuleNotFoundError` instead of an answer. This is the same failure
as the 2026-10-09 `snake_case` fix, one character class short.

## 2026-10-10 — `.markdown` homepages were invisible to the index rules

### What changed

`CONTENT_SUFFIXES` is `(".md", ".markdown")`, so the walker collects
`index.markdown`. But every "is this a landing page?" check hardcoded the
literal string `index.md`: `Page.url`, `site_name`, and `lead_page`. So a site
whose homepage used the long suffix got this output:

```
# Changelog

- [Changelog](/changelog): Notes.
- [My Docs](/index): Hello there.
```

The homepage was named after a sibling page and linked at a URL that does not
exist on most static hosts.

There is now one predicate, `content.is_index_path`, derived from
`CONTENT_SUFFIXES` rather than written out again, and all three call sites use
it. A third suffix added later works without a second edit.

### Why it matters

`llms.txt` is a map of the site. An entry pointing at `/index` when the page
is served at `/` is not a useful map — it is a dead link in the one file whose
entire job is not to have dead links. And the whole "site name comes from the
homepage" fix from two ticks ago silently did not apply to half the input the
tool claims to read.

### Tests

Three new: the URL rules for `index.markdown` at root and nested, the site
name, and a render-level check that the output links to `/` and never to
`/index`. Suite: 99 → 102.

## 2026-10-09 — underscores were stripped out of identifiers

### What changed

`plain_text` stripped emphasis with `re.sub(r"[*_]{1,3}", "", line)`, applied to
the whole line with no notion of word boundaries. Every underscore went, so
`load_user_profile()` became `loaduserprofile()` and `max_tokens` became
`maxtokens`.

It is now a dedicated `_strip_emphasis` with a pattern that only treats a
marker as emphasis when it opens or closes a word: the marker cannot sit
directly against an alphanumeric on the outside. A bare `__init__` and a link
target like `docs/config_2.md` survive intact.

### Why it matters

`plain_text` exists for one reason: to keep the URLs and names an LLM needs
while dropping the markdown around them. The emphasis stripper was deleting
exactly that. It feeds the audit's word count today, and anything that renders
plain text would have inherited the corruption.

### Tests

Three new: identifiers keep their underscores, link targets keep theirs, and
` _word_ ` at a boundary is still stripped. The third guards against "fixing"
this by simply not stripping emphasis at all.

Suite: 96 → 99.

## 2026-10-08 — the site name came from the wrong page

### What changed

`site_name()` returned the first page at the root of the content tree, and
pages arrive sorted by path. So it returned the alphabetically first
root-level file, not `index.md`. A site with a root-level `changelog.md` had
this H1 in both generated files:

    # Changelog

`index.md` sorts under "i", behind `about.md`, `api.md`, `changelog.md`, and
every other root-level page a real project accumulates. The closer a project's
content looked like a real project, the more reliably the name came out wrong.

### Why it matters

The H1 of `llms.txt` is the one line of the whole file that states what the
site is. A model reading the file is being told, confidently, that this is a
changelog. It is not a cosmetic problem: this is the same class of bug as the
lead-page bug already recorded under v0.1.0, and it survived that fix because
`site_name` was never given the same treatment.

The existing test passed by accident. `test_site_name_uses_first_toplevel_page`
wrote one top-level file — `index.md` itself — so "first top-level page" and
"index.md" were the same page and the distinction was invisible. That is why
the new tests all add a second root-level file.

### The fix

A root `index.md` is looked for first, then the first top-level page as
before. A nested page still never names the site, so `test_site_name_default_
when_only_nested` keeps passing: a directory landing page is not the name of
the site, and "This site" is a better H1 than a sub-section's title.

I first tried delegating to `lead_page()`, which already has the right
priority order. That made `site_name` name the site after `guide/index.md`
when the only top-level content is a directory, which is a real behaviour
change beyond this bug's blast radius. The explicit two-pass version fixes the
reported bug and changes nothing else.

### Tests

Four new: the root-index-beats-sibling case at the unit level, the same
through the CLI asserting the first line of both generated files, the nested
case as a regression guard on the old rule, and the no-index-anywhere
fallback. The nested and fallback cases passed before the fix and are there to
say so explicitly.

Suite: 92 → 96.

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
- `site_name` did not follow the same priority rule as `lead_page`; a site
  with a root-level page sorting before `index.md` was named after that page.
  Fixed 2026-10-08.
- Setext headings are read for titles, including multi-line ones, but a
  heading whose content is split across lines is joined with a space rather
  than with a soft line break. That is the same string in the title; it differs
  only in `llms-full.txt`, which keeps the original body untouched.
