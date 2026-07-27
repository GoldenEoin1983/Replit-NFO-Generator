#!/usr/bin/env python3
"""
Markdown upkeep checker.

Scans all .md files in the repo and reports:
  - Internal links ([text](path)) that point to missing files
  - Code blocks that reference filenames not present in the repo
  - Empty sections (headings with no content before the next heading)
  - Duplicate headings within a file

Usage:
  python scripts/check_md.py            # check all .md files
  python scripts/check_md.py README.md  # check one file
  python scripts/check_md.py --fix      # auto-fix what can be fixed (currently: trailing whitespace)
"""

import argparse
import re
import sys
from pathlib import Path

# Repo root = parent of the scripts/ directory
ROOT = Path(__file__).parent.parent


def find_md_files(paths: list[Path]) -> list[Path]:
    """Return all .md files to check."""
    if paths:
        return [p for p in paths if p.suffix == ".md"]
    return sorted(ROOT.glob("**/*.md"), key=lambda p: str(p))


def _skip(path: Path) -> bool:
    """Return True if this file should be skipped."""
    skip_dirs = {"__pycache__", "node_modules"}
    skip_files = {"replit.md"}
    # Skip anything inside a hidden folder (.git, .cache, .local, ...) too
    hidden = any(part.startswith(".") for part in path.parent.parts)
    return (hidden
            or any(part in skip_dirs for part in path.parts)
            or path.name in skip_files)


# ── Checks ────────────────────────────────────────────────────────────────────

def check_internal_links(path: Path, lines: list[str]) -> list[str]:
    """Warn when [text](target) points to a non-existent local file."""
    issues = []
    link_re = re.compile(r'\[([^\]]+)\]\(([^)#]+)(?:#[^)]*)?\)')
    for i, line in enumerate(lines, 1):
        for _, target in link_re.findall(line):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                issues.append(f"  line {i}: broken link -> '{target}'")
    return issues


def check_code_block_files(path: Path, content: str) -> list[str]:
    """Warn when a code block contains a bare filename that doesn't exist in the repo."""
    issues = []
    # Match fenced code blocks
    block_re = re.compile(r'```[^\n]*\n(.*?)```', re.DOTALL)
    # Pattern for filenames: word.ext on its own line, not a shell command
    file_re = re.compile(r'^\s*([\w/-]+\.\w+)\s*$', re.MULTILINE)
    skip_exts = {".nfo", ".jpg", ".png", ".gif", ".webp", ".mp4", ".mkv", ".avi"}

    for block in block_re.finditer(content):
        for m in file_re.finditer(block.group(1)):
            fname = m.group(1).strip()
            if Path(fname).suffix in skip_exts:
                continue
            candidate = ROOT / fname
            if not candidate.exists():
                issues.append(f"  code block references missing file: '{fname}'")
    return issues


def check_empty_sections(path: Path, lines: list[str]) -> list[str]:
    """Warn when a heading is immediately followed by another heading with no blank line between."""
    issues = []
    heading_re = re.compile(r'^#{1,6}\s')
    for i in range(len(lines) - 1):
        if heading_re.match(lines[i]) and heading_re.match(lines[i + 1]):
            issues.append(
                f"  line {i + 1}: heading immediately followed by heading on line {i + 2} (no content or blank line)"
            )
    return issues


def check_duplicate_headings(path: Path, lines: list[str]) -> list[str]:
    """Warn when the same heading text appears more than once in a file."""
    issues = []
    heading_re = re.compile(r'^#{1,6}\s+(.*)')
    seen: dict[str, int] = {}
    for i, line in enumerate(lines, 1):
        m = heading_re.match(line.strip())
        if m:
            text = m.group(1).strip().lower()
            if text in seen:
                issues.append(f"  line {i}: duplicate heading '{m.group(1).strip()}' (first at line {seen[text]})")
            else:
                seen[text] = i
    return issues


# ── Fix ───────────────────────────────────────────────────────────────────────

def fix_trailing_whitespace(path: Path, content: str) -> tuple[str, int]:
    """Remove trailing whitespace from non-blank lines."""
    lines = content.splitlines(keepends=True)
    fixed = []
    count = 0
    for line in lines:
        stripped = line.rstrip(" \t")
        if line.endswith("\n"):
            stripped += "\n"
        if stripped != line:
            count += 1
        fixed.append(stripped)
    return "".join(fixed), count


# ── Runner ────────────────────────────────────────────────────────────────────

def check_file(path: Path, fix: bool = False) -> int:
    """Run all checks on one file. Returns number of issues found."""
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"{path}: ERROR reading file — {e}")
        return 1

    lines = content.splitlines()
    all_issues: list[str] = []

    all_issues += check_internal_links(path, lines)
    all_issues += check_code_block_files(path, content)
    all_issues += check_empty_sections(path, lines)
    all_issues += check_duplicate_headings(path, lines)

    rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path

    if fix:
        new_content, n = fix_trailing_whitespace(path, content)
        if n:
            path.write_text(new_content, encoding="utf-8")
            print(f"{rel}: fixed {n} trailing whitespace occurrence(s)")

    if all_issues:
        print(f"\n{rel}:")
        for issue in all_issues:
            print(issue)

    return len(all_issues)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Markdown files for common issues")
    parser.add_argument(
        "files", nargs="*", type=Path,
        help="Specific .md files to check (default: all .md files in the repo)"
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="Auto-fix what can be fixed (currently: trailing whitespace)"
    )
    args = parser.parse_args()

    md_files = [f for f in find_md_files(args.files) if not _skip(f)]

    if not md_files:
        print("No Markdown files found.")
        return 0

    total_issues = 0
    for path in md_files:
        total_issues += check_file(path, fix=args.fix)

    if total_issues == 0:
        print(f"All {len(md_files)} Markdown file(s) look good.")
    else:
        print(f"\n{total_issues} issue(s) found across {len(md_files)} file(s).")

    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
