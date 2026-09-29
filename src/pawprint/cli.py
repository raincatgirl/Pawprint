"""Command-line interface for Pawprint.

Three verbs, all offline by default:

    pawprint build  <root> [--out DIR]
    pawprint audit  <root>
    pawprint policy [<robots.txt>]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .audit import grade, run_checks, score, summarise
from .content import collect
from .crawlers import CRAWLERS, ROBOTS_SAMPLE, audit_policy, recommendations
from .render import render_full, render_index

DEFAULT_ROOT = "."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pawprint",
        description="Zero-dependency GEO toolkit: llms.txt generation and AI-readiness auditing.",
    )
    parser.add_argument("--version", action="version", version=f"pawprint {__version__}")
    sub = parser.add_subparsers(dest="command")

    build = sub.add_parser("build", help="generate llms.txt and llms-full.txt from a content tree")
    build.add_argument("root", nargs="?", default=DEFAULT_ROOT, help="content directory (default: .)")
    build.add_argument("--out", default=None, help="output directory (default: the content root)")
    build.add_argument("--name", default=None, help="site name for the H1")
    build.add_argument("--base-url", default="", help="origin prefix, e.g. https://example.com")
    build.add_argument("--include-drafts", action="store_true", help="include pages marked draft: true")
    build.add_argument("--json", action="store_true", help="emit a JSON summary instead of text")

    audit = sub.add_parser("audit", help="score how legible the site is to an AI engine")
    audit.add_argument("root", nargs="?", default=DEFAULT_ROOT, help="site root (default: .)")
    audit.add_argument("--include-drafts", action="store_true", help="include pages marked draft: true")
    audit.add_argument("--json", action="store_true", help="emit JSON instead of text")

    policy = sub.add_parser("policy", help="show which AI crawlers you allow or block")
    policy.add_argument("robots", nargs="?", default=None, help="path to robots.txt (default: ./robots.txt, else a sample)")
    policy.add_argument("--json", action="store_true", help="emit JSON instead of text")
    policy.add_argument("--fix", action="store_true", help="print a starter robots.txt instead of the table")

    return parser


def cmd_build(args: argparse.Namespace) -> int:
    pages = collect(args.root, include_drafts=args.include_drafts)
    out_dir = args.out or args.root
    os.makedirs(out_dir, exist_ok=True)

    index = render_index(pages, name=args.name, base_url=args.base_url)
    full = render_full(pages, name=args.name)

    index_path = os.path.join(out_dir, "llms.txt")
    full_path = os.path.join(out_dir, "llms-full.txt")
    with open(index_path, "w", encoding="utf-8") as handle:
        handle.write(index)
    with open(full_path, "w", encoding="utf-8") as handle:
        handle.write(full)

    if args.json:
        print(json.dumps({
            "root": args.root,
            "out": out_dir,
            "pages": len(pages),
            "llms_txt": index_path,
            "llms_full_txt": full_path,
            "index_bytes": len(index.encode("utf-8")),
            "full_bytes": len(full.encode("utf-8")),
        }, indent=2, ensure_ascii=False))
        return 0

    print(f"Wrote {index_path} ({len(index.encode('utf-8'))} bytes, {len(pages)} pages)")
    print(f"Wrote {full_path} ({len(full.encode('utf-8'))} bytes)")
    if not pages.pages:
        print("\nNo content pages found. Point pawprint at a directory of .md files.")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    pages = collect(args.root, include_drafts=args.include_drafts)
    checks = run_checks(args.root, pages)
    total = score(checks)

    if args.json:
        print(json.dumps({
            "root": args.root,
            "score": total,
            "grade": grade(total),
            "pages": len(pages),
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail, "points": c.points}
                for c in checks
            ],
        }, indent=2, ensure_ascii=False))
        return 0

    print(summarise(checks, pages))
    return 0


def cmd_policy(args: argparse.Namespace) -> int:
    if args.fix:
        print(ROBOTS_SAMPLE)
        return 0

    path = args.robots
    if path is None:
        candidate = os.path.join(DEFAULT_ROOT, "robots.txt")
        path = candidate if os.path.exists(candidate) else None

    if path is None or not os.path.exists(path):
        text = ""
        source = "no robots.txt found — showing what a permissive one looks like"
    else:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            source = path
        except (OSError, UnicodeDecodeError) as exc:
            print(f"Could not read {path}: {exc}", file=sys.stderr)
            return 1

    rows = audit_policy(text)

    if args.json:
        print(json.dumps({
            "source": source,
            "crawlers": [
                {"name": n, "verdict": v, "note": note,
                 "purpose": next(c.purpose for c in CRAWLERS if c.name == n),
                 "want_allowed": next(c.want_allowed for c in CRAWLERS if c.name == n)}
                for n, v, note in rows
            ],
            "recommendations": recommendations(text),
        }, indent=2, ensure_ascii=False))
        return 0

    print(f"Crawler policy ({source})")
    print()
    name_width = max(len(n) for n, _, _ in rows)
    for name, state, note in rows:
        print(f"  {name.ljust(name_width)}  {state:<9} {note}")
    print()
    print("Recommendations:")
    for line in recommendations(text):
        print(f"  - {line}")
    print()
    print("Run `pawprint policy --fix` for a starter robots.txt.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    handler = {"build": cmd_build, "audit": cmd_audit, "policy": cmd_policy}[args.command]
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
